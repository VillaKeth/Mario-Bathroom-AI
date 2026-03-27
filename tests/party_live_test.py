#!/usr/bin/env python3
"""
Mario AI Party — 30-Minute Live Quality Monitor
Simulates realistic party guests, monitors response quality, 
emotion-pose alignment, audio validity, idle behavior, and features.

Usage:
    python party_live_test.py                  # Full 30-min simulation
    python party_live_test.py --duration 10    # 10-min simulation
    python party_live_test.py --quick          # 5-min quick check
"""

import asyncio
import json
import time
import random
import struct
import hashlib
import argparse
import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

import websockets
import requests

# ── Emotion-to-Pose Mapping (from client/mario_display.py) ──────────────
EMOTION_SPRITE_MAP = {
    "happy": "positive/happy",
    "excited": "positive/excited_jump",
    "surprised": "thinking/surprised",
    "confused": "thinking/confused",
    "annoyed": "negative/annoyed",
    "sleepy": "sleep/sleepy",
    "mischievous": "thinking/mischievous",
    "laughing": "positive/laughing",
    "sad": "negative/sad",
    "angry": "negative/angry",
    "nervous": "negative/nervous",
    "scared": "negative/scared",
    "love": "positive/love",
    "loving": "positive/love",
    "proud": "positive/proud",
    "embarrassed": "negative/embarrassed",
    "disgusted": "negative/disgusted",
    "determined": "thinking/determined",
    "bored": "sleep/yawning",
    "worried": "negative/nervous",
    "curious": "thinking/curious",
    "thinking": "thinking/thinking",
    "shocked": "thinking/shocked",
    "idea": "thinking/idea",
    "frustrated": "negative/annoyed",
    "neutral": "neutral/idle",
}

# Emotion → expected sentiment category
EMOTION_SENTIMENT = {
    "happy": "positive", "excited": "positive", "amused": "positive",
    "proud": "positive", "laughing": "positive", "love": "positive",
    "loving": "positive",
    "sad": "negative", "angry": "negative", "scared": "negative",
    "annoyed": "negative", "nervous": "negative", "disgusted": "negative",
    "frustrated": "negative", "embarrassed": "negative",
    "thinking": "neutral", "confused": "neutral", "curious": "neutral",
    "surprised": "neutral", "neutral": "neutral", "dramatic": "neutral",
    "bashful": "neutral", "mischievous": "neutral", "determined": "neutral",
}

# Categories of valid emotions the server can send
VALID_EMOTIONS = {
    "happy", "excited", "surprised", "thinking", "confused", "sad", "angry",
    "scared", "proud", "bashful", "amused", "dramatic", "neutral",
    "laughing", "love", "loving", "annoyed", "nervous", "embarrassed",
    "disgusted", "mischievous", "determined", "bored", "worried",
    "curious", "shocked", "idea", "frustrated", "sleepy",
}


@dataclass
class Interaction:
    """Records a single guest→Mario interaction."""
    timestamp: float = 0.0
    guest_name: str = ""
    message_sent: str = ""
    scenario: str = ""
    response_text: str = ""
    response_time: float = 0.0
    emotion: str = ""
    emotion_intensity: float = 0.0
    pose_hint: str = ""
    audio_chunks: int = 0
    audio_bytes: int = 0
    is_thinking_filler: bool = False
    
    # Quality assessments
    in_character: bool = True
    emotion_appropriate: bool = True
    audio_valid: bool = True
    notes: list = field(default_factory=list)


@dataclass
class IdleObservation:
    """Records an idle behavior message."""
    timestamp: float = 0.0
    text: str = ""
    emotion: str = ""
    category: str = ""  # mumble, song, joke, trivia, challenge, etc.
    seconds_since_last: float = 0.0


@dataclass 
class QualityReport:
    """Aggregated quality report."""
    duration_minutes: float = 0.0
    interactions: list = field(default_factory=list)
    idle_observations: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    
    # Aggregate metrics
    total_interactions: int = 0
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    in_character_rate: float = 0.0
    emotion_accuracy_rate: float = 0.0
    audio_success_rate: float = 0.0
    unique_emotions_seen: set = field(default_factory=set)
    idle_message_count: int = 0
    idle_unique_messages: int = 0
    features_tested: set = field(default_factory=set)


# ── Party Scenarios ──────────────────────────────────────────────────────
PARTY_SCENARIOS = [
    # (scenario_name, message, expected_emotion_category, feature_tag)
    ("greeting", "Hey Mario! What's up!", "positive", "chat"),
    ("name_intro", None, None, "name"),  # special: set_name then greet
    ("casual_chat", "So what do you think about this party?", "positive", "chat"),
    ("compliment", "Dude your mustache is absolutely legendary", "positive", "chat"),
    ("question_lore", "What's the deal with Bowser? Why does he keep taking Peach?", None, "chat"),
    ("question_deep", "What's it like living in the Mushroom Kingdom?", "positive", "chat"),
    ("joke_request", "Tell me your best joke Mario!", "positive", "chat"),
    ("song_request", "Sing me a song!", "positive", "chat"),
    ("selfie_request", "Can I take a selfie with you?", "positive", "chat"),
    ("bathroom_humor", "Why is there a Mario in the bathroom of all places?", "positive", "chat"),
    ("kid_question", "Are you the REAL Mario?!", "positive", "chat"),
    ("drunk_guest", "Bro you are literally the GOAT, like THE best character ever made", "positive", "chat"),
    ("challenge", "I bet I could beat you in a race around the Mushroom Kingdom", "positive", "chat"),
    ("crossover", "Have you ever met Sonic? Who would win in a fight?", None, "chat"),
    ("nostalgia", "I've been playing your games since I was 5 years old", "positive", "chat"),
    ("game_20q", "Let's play 20 questions!", None, "game"),
    ("game_trivia", "Quiz me on Mario trivia!", None, "game"),
    ("game_rps", "Rock paper scissors, let's go!", None, "game"),
    ("game_truth_dare", "Truth or dare Mario!", None, "game"),
    ("game_riddle", "Tell me a riddle!", None, "game"),
    ("game_simon", "Let's play Simon says!", None, "game"),
    ("returning_guest", "I'm back! Did you miss me?", "positive", "memory"),
    ("remember_me", "Do you remember what we talked about earlier?", None, "memory"),
    ("complaint", "It's so hot in here, the bathroom is tiny", None, "chat"),
    ("weird_question", "If you could eat any power-up for breakfast what would it be?", None, "chat"),
    ("philosophy", "Do you ever wonder if you're just a character in a game?", "neutral", "chat"),
    ("farewell", "Alright gotta go, bye Mario!", "positive", "chat"),
    ("group_arrive", "Hey everyone look who's in the bathroom! It's Mario!", "positive", "chat"),
    ("rapid_fire", "Quick! Favorite color? Favorite food? Favorite game?", None, "chat"),
    ("emotional_test", "I'm feeling kind of down today, cheer me up Mario", "positive", "chat"),
]

GUEST_NAMES = [
    "Jake", "Sarah", "Mike", "Emma", "Chris", "Olivia", "Tyler", "Mia",
    "Brandon", "Sophia", "Alex", "Ava", "Jordan", "Isabella", "Dylan",
    "Chloe", "Austin", "Lily", "Hunter", "Zoe"
]


def print_header(text, char="═"):
    width = 70
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


def print_subheader(text):
    print(f"\n{'─' * 50}")
    print(f"  {text}")
    print(f"{'─' * 50}")


def assess_in_character(text: str) -> tuple:
    """Check if Mario's response sounds in-character."""
    issues = []
    text_lower = text.lower()
    
    # Should have some Mario personality markers (at least occasionally)
    mario_markers = [
        "mama", "mia", "wahoo", "luigi", "princess", "peach", "bowser",
        "mushroom", "kingdom", "pipe", "coin", "star", "power", "super",
        "it's-a me", "letsa", "okey-dokey", "yahoo", "here we go",
        "fire", "warp", "goomba", "koopa", "toad", "yoshi", "!",
        "plumber", "pasta", "italian", "adventure", "hero", "brave"
    ]
    
    # Red flags that Mario should NOT say
    red_flags = [
        "as an ai", "as a language model", "i'm an ai", "i cannot",
        "i don't have feelings", "i'm not real", "i'm just a program",
        "openai", "chatgpt", "claude", "anthropic"
    ]
    
    has_personality = any(m in text_lower for m in mario_markers)
    has_red_flag = any(rf in text_lower for rf in red_flags)
    
    if has_red_flag:
        issues.append("BROKE CHARACTER — AI self-reference detected")
    
    # Don't require markers in every response, but flag if missing
    in_char = not has_red_flag
    if not has_personality and len(text) > 100:
        issues.append("Low Mario personality (no markers in long response)")
    
    return in_char, issues


def assess_emotion_appropriateness(emotion: str, scenario: str, text: str) -> tuple:
    """Check if the emotion matches the scenario context."""
    issues = []
    appropriate = True
    
    # Scenarios that should generally be positive
    positive_scenarios = {"greeting", "compliment", "kid_question", "nostalgia", 
                         "song_request", "joke_request", "selfie_request", "returning_guest",
                         "emotional_test", "drunk_guest"}
    
    # Get emotion sentiment
    sentiment = EMOTION_SENTIMENT.get(emotion, "neutral")
    
    if scenario in positive_scenarios and sentiment == "negative":
        # Mario should not be sad/angry when someone is being nice
        issues.append(f"Negative emotion '{emotion}' for positive scenario '{scenario}'")
        appropriate = False
    
    # Validate emotion is known
    if emotion and emotion not in VALID_EMOTIONS:
        issues.append(f"Unknown emotion: '{emotion}'")
        appropriate = False
    
    return appropriate, issues


def validate_audio(audio_bytes: int, audio_chunks: int) -> tuple:
    """Validate audio response quality."""
    issues = []
    valid = True
    
    if audio_chunks == 0:
        issues.append("No audio received")
        valid = False
    elif audio_bytes < 1000:
        issues.append(f"Audio too small ({audio_bytes} bytes) — may be empty/corrupt")
        valid = False
    elif audio_bytes > 5_000_000:
        issues.append(f"Audio unusually large ({audio_bytes/1e6:.1f}MB)")
    
    return valid, issues


class PartySimulator:
    """Simulates a realistic party with quality monitoring."""
    
    def __init__(self, server_url="ws://localhost:8765/ws", duration_minutes=30):
        self.server_url = server_url
        self.duration_minutes = duration_minutes
        self.report = QualityReport()
        self.ws = None
        self._response_texts = []
        self._response_emotions = []
        self._audio_chunks = []
        self._audio_bytes = 0
        self._idle_texts = []
        self._last_interaction_time = 0
        self._start_time = 0
        self._guest_name = ""
        self._pose_hint = ""
        
    async def connect(self, name="TestGuest"):
        """Connect to Mario server."""
        self.ws = await websockets.connect(self.server_url, max_size=10*1024*1024)
        self._guest_name = name
        print(f"  ✓ Connected as '{name}'")
        return True
        
    async def disconnect(self):
        """Disconnect cleanly."""
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "presence_exit"}))
                await asyncio.sleep(1)
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
            
    async def send_presence_enter(self):
        """Enter the bathroom."""
        await self.ws.send(json.dumps({"type": "presence_enter"}))
        
    async def set_name(self, name):
        """Set guest name via speaker identification."""
        self._guest_name = name
        await self.ws.send(json.dumps({"type": "set_name", "name": name}))
        
    async def send_text(self, text):
        """Send a text message to Mario."""
        await self.ws.send(json.dumps({"type": "text_input", "text": text}))
        
    async def collect_response(self, timeout=50, quiet_gap=8):
        """Collect Mario's full response (text + audio)."""
        texts = []
        emotions = []
        audio_chunks = 0
        audio_bytes_total = 0
        pose_hint = ""
        is_filler = False
        last_msg_time = time.time()
        start = time.time()
        
        try:
            while True:
                remaining = timeout - (time.time() - start)
                if remaining <= 0:
                    break
                    
                quiet_elapsed = time.time() - last_msg_time
                if quiet_elapsed > quiet_gap and (texts or audio_chunks > 0):
                    break
                    
                try:
                    msg = await asyncio.wait_for(self.ws.recv(), timeout=min(2.0, remaining))
                    last_msg_time = time.time()
                    
                    if isinstance(msg, bytes):
                        audio_chunks += 1
                        audio_bytes_total += len(msg)
                    else:
                        data = json.loads(msg)
                        msg_type = data.get("type", "")
                        
                        if msg_type == "mario_response":
                            text = data.get("text", "")
                            if text:
                                texts.append(text)
                            em = data.get("emotion", "")
                            if em:
                                emotions.append(em)
                            meta = data.get("metadata", {})
                            if meta.get("pose_hint"):
                                pose_hint = meta["pose_hint"]
                            if data.get("is_thinking_filler"):
                                is_filler = True
                                
                        elif msg_type == "idle_message":
                            idle_text = data.get("text", "")
                            idle_emotion = data.get("emotion", "")
                            if idle_text:
                                self._idle_texts.append({
                                    "text": idle_text,
                                    "emotion": idle_emotion,
                                    "time": time.time()
                                })
                                
                except asyncio.TimeoutError:
                    continue
                    
        except Exception as e:
            self.report.errors.append(f"collect_response error: {e}")
            
        return {
            "texts": texts,
            "full_text": " ".join(texts),
            "emotions": emotions,
            "primary_emotion": emotions[0] if emotions else "neutral",
            "audio_chunks": audio_chunks,
            "audio_bytes": audio_bytes_total,
            "pose_hint": pose_hint,
            "is_filler": is_filler,
            "response_time": time.time() - start,
        }
        
    async def monitor_idle(self, duration_seconds=60):
        """Monitor idle messages for a period."""
        idle_msgs = []
        start = time.time()
        
        try:
            while time.time() - start < duration_seconds:
                try:
                    msg = await asyncio.wait_for(self.ws.recv(), timeout=3.0)
                    if isinstance(msg, str):
                        data = json.loads(msg)
                        if data.get("type") in ("mario_response", "idle_message"):
                            text = data.get("text", "")
                            emotion = data.get("emotion", "")
                            if text:
                                obs = IdleObservation(
                                    timestamp=time.time(),
                                    text=text,
                                    emotion=emotion,
                                    seconds_since_last=(time.time() - start if not idle_msgs 
                                                       else time.time() - idle_msgs[-1].timestamp)
                                )
                                idle_msgs.append(obs)
                                elapsed = time.time() - start
                                print(f"    [{elapsed:.0f}s] IDLE: [{emotion}] {text[:80]}")
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            self.report.errors.append(f"monitor_idle error: {e}")
            
        return idle_msgs
    
    async def run_interaction(self, scenario_name, message, expected_sentiment, feature_tag):
        """Run a single party interaction and assess quality."""
        interaction = Interaction(
            timestamp=time.time(),
            guest_name=self._guest_name,
            message_sent=message,
            scenario=scenario_name,
        )
        
        print(f"\n  🎤 Guest ({self._guest_name}): \"{message}\"")
        
        # Send message
        t0 = time.time()
        await self.send_text(message)
        
        # Collect response
        resp = await self.collect_response()
        interaction.response_time = resp["response_time"]
        interaction.response_text = resp["full_text"]
        interaction.emotion = resp["primary_emotion"]
        interaction.audio_chunks = resp["audio_chunks"]
        interaction.audio_bytes = resp["audio_bytes"]
        interaction.pose_hint = resp["pose_hint"]
        interaction.is_thinking_filler = resp["is_filler"]
        
        # Assess quality
        if resp["full_text"]:
            in_char, char_issues = assess_in_character(resp["full_text"])
            interaction.in_character = in_char
            interaction.notes.extend(char_issues)
        else:
            interaction.in_character = False
            interaction.notes.append("No text response received")
            
        emotion_ok, em_issues = assess_emotion_appropriateness(
            resp["primary_emotion"], scenario_name, resp["full_text"]
        )
        interaction.emotion_appropriate = emotion_ok
        interaction.notes.extend(em_issues)
        
        audio_ok, audio_issues = validate_audio(resp["audio_bytes"], resp["audio_chunks"])
        interaction.audio_valid = audio_ok
        interaction.notes.extend(audio_issues)
        
        # Track emotions
        for em in resp["emotions"]:
            self.report.unique_emotions_seen.add(em)
            
        self.report.features_tested.add(feature_tag)
        
        # Print result
        status = "✅" if (interaction.in_character and interaction.emotion_appropriate and interaction.audio_valid) else "⚠️"
        text_preview = resp["full_text"][:120] + "..." if len(resp["full_text"]) > 120 else resp["full_text"]
        print(f"  {status} Mario [{resp['primary_emotion']}]: \"{text_preview}\"")
        print(f"     ⏱️ {resp['response_time']:.1f}s | 🔊 {resp['audio_chunks']} chunks ({resp['audio_bytes']/1024:.1f}KB)", end="")
        if resp["pose_hint"]:
            print(f" | 🎭 pose: {resp['pose_hint']}", end="")
        print()
        
        if interaction.notes:
            for note in interaction.notes:
                print(f"     ⚠️  {note}")
                
        self.report.interactions.append(interaction)
        return interaction
    
    async def run_simulation(self):
        """Run the full party simulation."""
        self._start_time = time.time()
        end_time = self._start_time + (self.duration_minutes * 60)
        
        print_header(f"🍄 MARIO PARTY LIVE TEST — {self.duration_minutes} Minutes")
        print(f"  Server: {self.server_url}")
        print(f"  Started: {datetime.now().strftime('%H:%M:%S')}")
        print(f"  Target end: {(datetime.now() + timedelta(minutes=self.duration_minutes)).strftime('%H:%M:%S')}")
        
        # ── Phase 1: Server Health ──
        print_subheader("Phase 1: Server Health Check")
        try:
            health = requests.get("http://localhost:8765/health", timeout=5).json()
            print(f"  ✓ Status: {health['status']}")
            print(f"  ✓ Cache: {health['tts_cache_size']} entries")
            print(f"  ✓ Model: {health['llm_model']}")
            print(f"  ✓ Emotion: {health['emotion']}")
            self.report.features_tested.add("health")
        except Exception as e:
            print(f"  ✗ Health check failed: {e}")
            self.report.errors.append(f"Health check failed: {e}")
            return self.report
        
        # ── Phase 2: First Guest Arrives ──
        print_subheader("Phase 2: First Guest Arrives — Greeting Test")
        guest_name = random.choice(GUEST_NAMES)
        await self.connect(guest_name)
        await self.set_name(guest_name)
        await asyncio.sleep(1)
        await self.send_presence_enter()
        
        print(f"  👤 {guest_name} enters the bathroom...")
        greeting_resp = await self.collect_response(timeout=45)
        
        if greeting_resp["full_text"]:
            print(f"  ✅ Mario: \"{greeting_resp['full_text'][:150]}\"")
            print(f"     ⏱️ {greeting_resp['response_time']:.1f}s | [{greeting_resp['primary_emotion']}] | 🔊 {greeting_resp['audio_chunks']} chunks")
            self.report.features_tested.add("greeting")
        else:
            print(f"  ⚠️ No greeting received in 45s")
            self.report.errors.append("No greeting received")
        
        await asyncio.sleep(3)  # Natural pause after greeting
        
        # ── Phase 3: Interactive Conversations ──
        print_subheader("Phase 3: Party Conversations")
        
        # Shuffle scenarios for natural feel
        scenarios = list(PARTY_SCENARIOS)
        random.shuffle(scenarios)
        
        interaction_count = 0
        guest_rotation = 0
        
        for scenario_name, message, expected_sent, feature_tag in scenarios:
            if time.time() >= end_time:
                print(f"\n  ⏰ Time's up! ({self.duration_minutes} minutes elapsed)")
                break
                
            # Handle special scenarios
            if scenario_name == "name_intro":
                new_name = random.choice([n for n in GUEST_NAMES if n != self._guest_name])
                message = f"Hey I'm {new_name}, nice to meet you!"
                await self.set_name(new_name)
                self._guest_name = new_name
                feature_tag = "name"
                
            # Every 8 interactions, simulate guest rotation
            if interaction_count > 0 and interaction_count % 8 == 0:
                guest_rotation += 1
                print(f"\n  🚪 --- Guest rotation #{guest_rotation} ---")
                
                # Disconnect current guest
                await self.ws.send(json.dumps({"type": "presence_exit"}))
                await asyncio.sleep(2)
                
                # Brief idle monitoring between guests
                print(f"  👀 Monitoring idle behavior (30s gap between guests)...")
                idle_msgs = await self.monitor_idle(30)
                self.report.idle_observations.extend(idle_msgs)
                
                # New guest arrives
                new_name = random.choice([n for n in GUEST_NAMES if n != self._guest_name])
                self._guest_name = new_name
                await self.set_name(new_name)
                await self.send_presence_enter()
                
                print(f"  👤 {new_name} enters!")
                greeting = await self.collect_response(timeout=40)
                if greeting["full_text"]:
                    print(f"  ✅ Mario greets {new_name}: \"{greeting['full_text'][:100]}\"")
                    self.report.features_tested.add("guest_rotation")
                    
                await asyncio.sleep(3)
            
            # Send the interaction
            await asyncio.sleep(random.uniform(3, 8))  # Natural pause between messages
            
            if message:
                await self.run_interaction(scenario_name, message, expected_sent, feature_tag)
                interaction_count += 1
                
                # Cooldown: server needs >2s between text inputs
                await asyncio.sleep(random.uniform(3, 5))
                
        # ── Phase 4: Extended Idle Monitoring ──
        remaining = end_time - time.time()
        if remaining > 30:
            idle_monitor_time = min(remaining - 10, 120)  # Up to 2 min of idle
            print_subheader(f"Phase 4: Idle Monitoring ({idle_monitor_time:.0f}s)")
            
            # Exit presence to trigger proper idle behavior
            await self.ws.send(json.dumps({"type": "presence_exit"}))
            await asyncio.sleep(2)
            
            idle_msgs = await self.monitor_idle(idle_monitor_time)
            self.report.idle_observations.extend(idle_msgs)
            self.report.features_tested.add("idle")
            
            if idle_msgs:
                print(f"\n  ✓ Received {len(idle_msgs)} idle messages")
                unique_idle = set(m.text for m in idle_msgs)
                print(f"  ✓ {len(unique_idle)} unique messages (dedup working: {'✅' if len(unique_idle) >= len(idle_msgs)*0.7 else '⚠️'})")
                
                # Check intervals
                intervals = [m.seconds_since_last for m in idle_msgs[1:]]
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    print(f"  ✓ Avg interval: {avg_interval:.1f}s (expected 15-90s)")
            else:
                print(f"  ⚠️ No idle messages received in {idle_monitor_time:.0f}s")
        
        # ── Phase 5: Final Health Check ──
        print_subheader("Phase 5: Final Health + Leaderboard Check")
        try:
            health = requests.get("http://localhost:8765/health", timeout=5).json()
            print(f"  ✓ Server still healthy: {health['status']}")
            print(f"  ✓ Total visits: {health.get('total_visits', 'N/A')}")
            print(f"  ✓ Total responses: {health.get('total_responses', 'N/A')}")
            print(f"  ✓ Cache hit rate: {health.get('tts_cache_hit_rate', 'N/A')}")
            
            stats = requests.get("http://localhost:8765/stats", timeout=5).json()
            if "leaderboard" in stats:
                print(f"  ✓ Leaderboard entries: {len(stats.get('leaderboard', []))}")
                self.report.features_tested.add("leaderboard")
        except Exception as e:
            print(f"  ⚠️ Final health check error: {e}")
            self.report.errors.append(f"Final health: {e}")
            
        # Disconnect
        await self.disconnect()
        
        # ── Generate Report ──
        self._generate_report()
        
        return self.report
    
    def _generate_report(self):
        """Generate and print the quality report."""
        r = self.report
        r.duration_minutes = (time.time() - self._start_time) / 60
        r.total_interactions = len(r.interactions)
        
        if r.interactions:
            r.avg_response_time = sum(i.response_time for i in r.interactions) / len(r.interactions)
            r.max_response_time = max(i.response_time for i in r.interactions)
            r.in_character_rate = sum(1 for i in r.interactions if i.in_character) / len(r.interactions)
            r.emotion_accuracy_rate = sum(1 for i in r.interactions if i.emotion_appropriate) / len(r.interactions)
            r.audio_success_rate = sum(1 for i in r.interactions if i.audio_valid) / len(r.interactions)
            
        r.idle_message_count = len(r.idle_observations)
        r.idle_unique_messages = len(set(o.text for o in r.idle_observations))
        
        print_header("📊 QUALITY REPORT", "█")
        print(f"""
  Duration:           {r.duration_minutes:.1f} minutes
  Interactions:       {r.total_interactions}
  Avg Response Time:  {r.avg_response_time:.1f}s
  Max Response Time:  {r.max_response_time:.1f}s
  
  CHARACTER QUALITY
  ─────────────────
  In-Character Rate:  {r.in_character_rate*100:.0f}% {'✅' if r.in_character_rate >= 0.9 else '⚠️'}
  Emotion Accuracy:   {r.emotion_accuracy_rate*100:.0f}% {'✅' if r.emotion_accuracy_rate >= 0.85 else '⚠️'}
  Audio Success:      {r.audio_success_rate*100:.0f}% {'✅' if r.audio_success_rate >= 0.9 else '⚠️'}
  Unique Emotions:    {len(r.unique_emotions_seen)} ({', '.join(sorted(r.unique_emotions_seen))})
  
  IDLE BEHAVIOR
  ─────────────
  Idle Messages:      {r.idle_message_count}
  Unique Messages:    {r.idle_unique_messages}
  
  FEATURES TESTED
  ───────────────
  {', '.join(sorted(r.features_tested))}
  
  ERRORS
  ──────
  {len(r.errors)} errors""")
        
        if r.errors:
            for err in r.errors:
                print(f"    ✗ {err}")
        
        # Problem interactions
        problems = [i for i in r.interactions if not i.in_character or not i.emotion_appropriate or not i.audio_valid]
        if problems:
            print(f"\n  PROBLEM INTERACTIONS ({len(problems)})")
            print(f"  {'─' * 40}")
            for p in problems:
                print(f"    [{p.scenario}] \"{p.message_sent[:50]}\"")
                for note in p.notes:
                    print(f"      → {note}")
        
        # Overall verdict
        all_good = (r.in_character_rate >= 0.9 and r.emotion_accuracy_rate >= 0.85 
                    and r.audio_success_rate >= 0.9 and len(r.errors) <= 2)
        
        if all_good:
            print(f"\n  {'═' * 50}")
            print(f"  🌟 VERDICT: PARTY READY! Mario is good to go! 🌟")
            print(f"  {'═' * 50}")
        else:
            print(f"\n  {'═' * 50}")
            print(f"  ⚠️  VERDICT: Issues found — review above")
            print(f"  {'═' * 50}")
            
        return all_good


async def main():
    parser = argparse.ArgumentParser(description="Mario Party Live Quality Monitor")
    parser.add_argument("--duration", type=int, default=30, help="Duration in minutes (default: 30)")
    parser.add_argument("--quick", action="store_true", help="Quick 5-minute check")
    parser.add_argument("--server", default="ws://localhost:8765/ws", help="Server WebSocket URL")
    args = parser.parse_args()
    
    duration = 5 if args.quick else args.duration
    
    sim = PartySimulator(server_url=args.server, duration_minutes=duration)
    
    try:
        report = await sim.run_simulation()
    except KeyboardInterrupt:
        print("\n\n  ⏹️  Test interrupted by user")
        sim._generate_report()
    except Exception as e:
        print(f"\n  ✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
