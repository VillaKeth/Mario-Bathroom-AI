"""Tests for person detection with Qdrant collections.

Tests face encoding and voice embedding storage/lookup using Qdrant
vector database for improved guest recognition and dynamic learning.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock

# Mock imports before importing our modules
mock_qdrant = MagicMock()
mock_models = MagicMock()
mock_resemblyzer = MagicMock()

# Make sure PointStruct returns a mock with expected attributes
mock_point_struct = MagicMock()
mock_models.PointStruct.return_value = mock_point_struct
# Add payload and vector attributes to the mock
mock_point_struct.payload = {}
mock_point_struct.vector = []

# Mock both the module and the direct imports
with patch.dict('sys.modules', {
    'qdrant_client': mock_qdrant,
    'qdrant_client.models': mock_models,
    'resemblyzer': mock_resemblyzer,
}):
    # Set up the mock objects to have the right attributes
    mock_qdrant.QdrantClient = MagicMock()
    mock_qdrant.models = mock_models
    mock_resemblyzer.VoiceEncoder = MagicMock()
    mock_resemblyzer.preprocess_wav = MagicMock()
    
    from server.face_memory import FaceMemory
    from server.speaker_id import init_speaker_id, get_embedding, identify_speaker, register_speaker


class TestFaceMemoryQdrant:
    """Test FaceMemory Qdrant collection integration."""

    def test_face_collection_init(self):
        """FaceMemory should initialize Qdrant collection for faces"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        mock_client = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        
        # Mock collections response - initially empty
        mock_client.get_collections.return_value.collections = []
        
        # Mock SQLite operations to prevent database creation
        with patch('sqlite3.connect') as mock_sqlite, \
             patch('os.makedirs') as mock_makedirs:
            
            mock_conn = MagicMock()
            mock_sqlite.return_value = mock_conn
            
            face_memory = FaceMemory("test.db")
            
            # Should have created QdrantClient
            mock_qdrant.QdrantClient.assert_called_once()
            assert face_memory._qdrant_client == mock_client

    def test_store_face_encoding(self):
        """Should store face encoding with guest name in Qdrant"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        mock_client = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Mock SQLite operations
        with patch('sqlite3.connect') as mock_sqlite, \
             patch('os.makedirs') as mock_makedirs:
            
            mock_conn = MagicMock()
            mock_sqlite.return_value = mock_conn
            
            face_memory = FaceMemory("test.db")
            
            # Test data
            name = "Jacob"
            encoding = np.random.random(128).astype(np.float64)
            
            # Call store_face_qdrant (new method)
            result = face_memory.store_face_qdrant(name, encoding)
            
            # Should have returned True (successful storage)
            assert result is True
            
            # Should have called upsert with face encoding
            mock_client.upsert.assert_called_once()
            
            # Verify the upsert was called with correct collection name
            args, kwargs = mock_client.upsert.call_args
            assert kwargs['collection_name'] == 'mario_faces'
            assert len(kwargs['points']) == 1
            
            # The point should be a mock object created by models.PointStruct
            assert mock_models.PointStruct.call_count >= 1

    def test_lookup_face_match(self):
        """Should find matching face in Qdrant by similarity"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        mock_client = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Mock successful search result
        mock_result = MagicMock()
        mock_point = MagicMock()
        mock_point.payload = {"name": "Jacob", "visits": 3}
        mock_point.score = 0.85
        mock_result.points = [mock_point]
        mock_client.query_points.return_value = mock_result
        
        # Mock SQLite operations
        with patch('sqlite3.connect') as mock_sqlite, \
             patch('os.makedirs') as mock_makedirs:
            
            mock_conn = MagicMock()
            mock_sqlite.return_value = mock_conn
            
            face_memory = FaceMemory("test.db")
            
            # Test lookup
            encoding = np.random.random(128).astype(np.float64)
            result = face_memory.lookup_face_qdrant(encoding)
            
            # Should return match
            assert result is not None
            assert result["name"] == "Jacob"
            assert result["confidence"] == 0.85
            assert result["visits"] == 3

    def test_lookup_face_no_match(self):
        """Should return None when no face matches above threshold"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        mock_client = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Mock empty search result
        mock_result = MagicMock()
        mock_result.points = []
        mock_client.query_points.return_value = mock_result
        
        # Mock SQLite operations
        with patch('sqlite3.connect') as mock_sqlite, \
             patch('os.makedirs') as mock_makedirs:
            
            mock_conn = MagicMock()
            mock_sqlite.return_value = mock_conn
            
            face_memory = FaceMemory("test.db")
            
            # Test lookup with no matches
            encoding = np.random.random(128).astype(np.float64)
            result = face_memory.lookup_face_qdrant(encoding)
            
            # Should return None
            assert result is None

    def test_learn_guest_face(self):
        """Should learn new guest face with incremental visit counter"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        mock_client = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Mock retrieve to return None (new guest)
        mock_client.retrieve.return_value = []
        
        # Mock SQLite completely to prevent any real database operations
        with patch('sqlite3.connect') as mock_sqlite, \
             patch('os.makedirs') as mock_makedirs, \
             patch.object(FaceMemory, 'store_face') as mock_store_face:
            
            mock_conn = MagicMock()
            mock_sqlite.return_value = mock_conn
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            mock_conn.execute.return_value.fetchone.return_value = [0]  # Max ID = 0
            
            face_memory = FaceMemory("test.db")
            
            # Test learning new guest
            name = "Alice"
            encoding = np.random.random(128).astype(np.float64)
            
            face_memory.learn_guest(name, encoding)
            
            # Should have stored in Qdrant
            assert mock_client.upsert.call_count >= 1
            
            # Should have also called store_face (SQLite fallback)
            mock_store_face.assert_called_once()
            
            # Verify the store_face call
            args, kwargs = mock_store_face.call_args
            assert args[1] == name  # Second argument should be name
            assert args[0] == 1     # First argument should be person_id = 1


class TestSpeakerIdQdrant:
    """Test SpeakerID Qdrant collection integration."""

    def test_voice_collection_init(self):
        """SpeakerID should initialize Qdrant collection for voices"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        mock_resemblyzer.reset_mock()
        
        mock_client = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        mock_client.get_collections.return_value.collections = []
        
        # Mock SQLite operations
        with patch('sqlite3.connect') as mock_sqlite, \
             patch('os.makedirs') as mock_makedirs:
            
            mock_conn = MagicMock()
            mock_sqlite.return_value = mock_conn
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            
            # Initialize speaker ID system
            init_speaker_id()
            
            # Should have created QdrantClient 
            mock_qdrant.QdrantClient.assert_called_once()
            
            # Should have created VoiceEncoder
            mock_resemblyzer.VoiceEncoder.assert_called_once()

    def test_store_voice_embedding(self):
        """Should store voice embedding with guest name"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        # Mock the global _qdrant_client variable that's set in init_speaker_id
        with patch('server.speaker_id._qdrant_client') as mock_client, \
             patch('sqlite3.connect') as mock_sqlite, \
             patch('os.makedirs') as mock_makedirs:
            
            mock_conn = MagicMock()
            mock_sqlite.return_value = mock_conn
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            mock_conn.execute.return_value.fetchone.return_value = None  # No existing speaker
            mock_conn.execute.return_value.lastrowid = 123  # New speaker ID
            
            mock_client.get_collections.return_value.collections = []
            
            # Import the function we'll test
            from server.speaker_id import store_voice_qdrant
            
            # Test data
            name = "Jacob"
            embedding = np.random.random(256).astype(np.float32)
            
            # Call store function
            result = store_voice_qdrant(name, embedding)
            
            # Should have returned True
            assert result is True
            
            # Should have called upsert
            mock_client.upsert.assert_called_once()
            
            # Verify parameters
            args, kwargs = mock_client.upsert.call_args
            assert kwargs['collection_name'] == 'mario_voices'

    def test_lookup_voice_match(self):
        """Should find matching voice by similarity"""
        # Reset mocks for clean test
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        # Mock the global _qdrant_client variable
        with patch('server.speaker_id._qdrant_client') as mock_client:
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

    def test_lookup_voice_no_match(self):
        """Should return None when no voice matches above threshold"""
        # Reset mocks for clean test  
        mock_qdrant.reset_mock()
        mock_models.reset_mock()
        
        # Mock the global _qdrant_client variable
        with patch('server.speaker_id._qdrant_client') as mock_client:
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