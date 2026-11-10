import unittest
from unittest.mock import patch
from src.brickforge.ingestion.registry import ProjectRegistry, SourceRoot

class TestProjectRegistry(unittest.TestCase):
    @patch.object(ProjectRegistry, '__init__', return_value=None)
    def test_project_registry_creation(self, mock_init):
        project = ProjectRegistry(
            id="123",
            user_id="user1",
            project_name="TestProject",
            source_roots=[SourceRoot(id="1", root_path="/path/to/source")],
            documentation_roots=["/path/to/docs"]
        )
        self.assertEqual(project.id, "123")
        self.assertEqual(project.user_id, "user1")
        self.assertEqual(project.project_name, "TestProject")
        self.assertEqual(len(project.source_roots), 1)
        self.assertEqual(len(project.documentation_roots), 1)

if __name__ == '__main__':
    unittest.main()
