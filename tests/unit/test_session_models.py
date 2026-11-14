import unittest
from brickforge.web.session_models import Session, SessionSource, Snapshot, Event, SourceKind, ProviderKind, RetentionState

class TestSessionModels(unittest.TestCase):

    def test_session_source_creation(self):
        source = SessionSource(kind=SourceKind.TEXT, uri="http://example.com/text")
        self.assertEqual(source.kind, SourceKind.TEXT)
        self.assertEqual(source.uri, "http://example.com/text")

    def test_snapshot_creation(self):
        snapshot = Snapshot(session_id=1, data={"key": "value"})
        self.assertEqual(snapshot.session_id, 1)
        self.assertEqual(snapshot.data, {"key": "value"})

    def test_event_creation(self):
        event = Event(session_id=1, type="test_event", details={"info": "test"})
        self.assertEqual(event.session_id, 1)
        self.assertEqual(event.type, "test_event")
        self.assertEqual(event.details, {"info": "test"})

    def test_session_creation(self):
        session = Session(
            user_id=1,
            sources=[SessionSource(kind=SourceKind.TEXT, uri="http://example.com/text")],
            snapshots=[Snapshot(session_id=1, data={"key": "value"})],
            events=[Event(session_id=1, type="test_event", details={"info": "test"})],
            provider=ProviderKind.OPENAI,
            model="gpt-3.5-turbo",
            retrieval_settings={"index": "default"},
            retention_state=RetentionState.ACTIVE
        )
        self.assertEqual(session.user_id, 1)
        self.assertEqual(len(session.sources), 1)
        self.assertEqual(len(session.snapshots), 1)
        self.assertEqual(len(session.events), 1)
        self.assertEqual(session.provider, ProviderKind.OPENAI)
        self.assertEqual(session.model, "gpt-3.5-turbo")
        self.assertEqual(session.retrieval_settings, {"index": "default"})
        self.assertEqual(session.retention_state, RetentionState.ACTIVE)

if __name__ == '__main__':
    unittest.main()
