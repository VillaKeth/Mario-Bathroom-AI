"""Tests for person detection with Qdrant collections.

Tests face encoding and voice embedding storage/lookup using Qdrant
vector database for improved guest recognition and dynamic learning.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock

# Mock qdrant imports before importing our modules
mock_qdrant = MagicMock()
mock_models = MagicMock()

with patch.dict('sys.modules', {
    'qdrant_client': mock_qdrant,
    'qdrant_client.models': mock_models
}):
    from server.face_memory import FaceMemory
    from server.speaker_id import init_speaker_id, get_embedding, identify_speaker, register_speaker


class TestFaceMemoryQdrant:
    """Test FaceMemory Qdrant collection integration."""

    def test_face_collection_init(self):
        """FaceMemory should initialize Qdrant collection for faces"""
        mock_client = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        
        # Mock collections response - initially empty
        mock_client.get_collections.return_value.collections = []
        
        face_memory = FaceMemory("test.db")
        
        # Should have created QdrantClient
        mock_qdrant.QdrantClient.assert_called_once()
        assert face_memory._qdrant_client == mock_client

    @patch('server.face_memory.QdrantClient')
    def test_store_face_encoding(self, mock_qdrant_client_class):
        """Should store face encoding with guest name in Qdrant"""
        mock_client = MagicMock()
        mock_qdrant_client_class.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        face_memory = FaceMemory("test.db")
        
        # Test data
        name = "Jacob"
        encoding = np.random.random(128).astype(np.float64)
        
        # Call store_face_qdrant (new method)
        face_memory.store_face_qdrant(name, encoding)
        
        # Should have called upsert with face encoding
        mock_client.upsert.assert_called_once()
        
        # Verify call parameters
        args, kwargs = mock_client.upsert.call_args
        assert kwargs['collection_name'] == 'mario_faces'
        point = kwargs['points'][0]
        assert point.payload['name'] == name
        assert len(point.vector) == 128

    @patch('server.face_memory.QdrantClient')
    def test_lookup_face_match(self, mock_qdrant_client_class):
        """Should find matching face in Qdrant by similarity"""
        mock_client = MagicMock()
        mock_qdrant_client_class.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Mock successful search result
        mock_result = MagicMock()
        mock_point = MagicMock()
        mock_point.payload = {"name": "Jacob", "visits": 3}
        mock_point.score = 0.85
        mock_result.points = [mock_point]
        mock_client.query_points.return_value = mock_result
        
        face_memory = FaceMemory("test.db")
        
        # Test lookup
        encoding = np.random.random(128).astype(np.float64)
        result = face_memory.lookup_face_qdrant(encoding)
        
        # Should return match
        assert result is not None
        assert result["name"] == "Jacob"
        assert result["confidence"] == 0.85
        assert result["visits"] == 3

    @patch('server.face_memory.QdrantClient')
    def test_lookup_face_no_match(self, mock_qdrant_client_class):
        """Should return None when no face matches above threshold"""
        mock_client = MagicMock()
        mock_qdrant_client_class.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Mock empty search result
        mock_result = MagicMock()
        mock_result.points = []
        mock_client.query_points.return_value = mock_result
        
        face_memory = FaceMemory("test.db")
        
        # Test lookup with no matches
        encoding = np.random.random(128).astype(np.float64)
        result = face_memory.lookup_face_qdrant(encoding)
        
        # Should return None
        assert result is None

    @patch('server.face_memory.QdrantClient')
    def test_learn_guest_face(self, mock_qdrant_client_class):
        """Should learn new guest face with incremental visit counter"""
        mock_client = MagicMock()
        mock_qdrant_client_class.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        face_memory = FaceMemory("test.db")
        
        # Test learning new guest
        name = "Alice"
        encoding = np.random.random(128).astype(np.float64)
        
        face_memory.learn_guest(name, encoding)
        
        # Should have stored in Qdrant
        mock_client.upsert.assert_called_once()
        
        # Verify stored data
        args, kwargs = mock_client.upsert.call_args
        point = kwargs['points'][0]
        assert point.payload['name'] == name
        assert point.payload['visits'] == 1


class TestSpeakerIdQdrant:
    """Test SpeakerID Qdrant collection integration."""

    @patch('server.speaker_id.VoiceEncoder')
    @patch('server.speaker_id.QdrantClient')
    def test_voice_collection_init(self, mock_qdrant_client_class, mock_voice_encoder):
        """SpeakerID should initialize Qdrant collection for voices"""
        mock_client = MagicMock()
        mock_qdrant_client_class.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Initialize speaker ID system
        init_speaker_id()
        
        # Should have created QdrantClient 
        mock_qdrant_client_class.assert_called_once()

    @patch('server.speaker_id._qdrant_client')
    def test_store_voice_embedding(self, mock_client):
        """Should store voice embedding with guest name"""
        # Import the function we'll test
        from server.speaker_id import store_voice_qdrant
        
        mock_client.get_collections.return_value.collections = []
        
        # Test data
        name = "Jacob"
        embedding = np.random.random(256).astype(np.float32)
        
        # Call store function
        store_voice_qdrant(name, embedding)
        
        # Should have called upsert
        mock_client.upsert.assert_called_once()
        
        # Verify parameters
        args, kwargs = mock_client.upsert.call_args
        assert kwargs['collection_name'] == 'mario_voices'
        point = kwargs['points'][0]
        assert point.payload['name'] == name
        assert len(point.vector) == 256

    @patch('server.speaker_id._qdrant_client')
    def test_lookup_voice_match(self, mock_client):
        """Should find matching voice by similarity"""
        # Import the function we'll test
        from server.speaker_id import lookup_voice_qdrant
        
        mock_client.get_collections.return_value.collections = []
        
        # Mock successful search result
        mock_result = MagicMock()
        mock_point = MagicMock()
        mock_point.payload = {"name": "Alice", "speaker_id": 123}
        mock_point.score = 0.82
        mock_result.points = [mock_point]
        mock_client.query_points.return_value = mock_result
        
        # Test lookup
        embedding = np.random.random(256).astype(np.float32)
        result = lookup_voice_qdrant(embedding)
        
        # Should return match
        assert result is not None
        assert result["name"] == "Alice"
        assert result["confidence"] == 0.82
        assert result["speaker_id"] == 123

    @patch('server.speaker_id._qdrant_client')
    def test_lookup_voice_no_match(self, mock_client):
        """Should return None when no voice matches above threshold"""
        # Import the function we'll test
        from server.speaker_id import lookup_voice_qdrant
        
        mock_client.get_collections.return_value.collections = []
        
        # Mock empty search result
        mock_result = MagicMock()
        mock_result.points = []
        mock_client.query_points.return_value = mock_result
        
        # Test lookup with no matches
        embedding = np.random.random(256).astype(np.float32)
        result = lookup_voice_qdrant(embedding)
        
        # Should return None
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])