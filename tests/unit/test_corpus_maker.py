"""Unit tests for Corpus Maker components."""
import pytest
import json
from pathlib import Path


class TestNormalizer:
    """Tests for folder and question normalization."""
    
    def test_normalizes_folder_names(self):
        from src.corpus_maker.normalizer import normalize_folder_name
        
        assert normalize_folder_name("All Docs") == "uncategorized"
        assert normalize_folder_name("all docs") == "uncategorized"
        assert normalize_folder_name("Strategy Documents") == "strategy"
        assert normalize_folder_name("Financial Reports") == "financials"
        assert normalize_folder_name("My Custom Folder") == "my_custom_folder"
        assert normalize_folder_name("  spaces  ") == "spaces"
        assert normalize_folder_name("Strategy-Documents") == "strategy_documents"
    
    def test_slugify(self):
        from src.corpus_maker.normalizer import slugify
        
        assert slugify("ClaudeCode Nexus Industries") == "claudecode_nexus_industries"
        assert slugify("My Test-Corpus") == "my_test_corpus"
        assert slugify("UPPERCASE") == "uppercase"
    
    def test_normalize_questions(self, tmp_path):
        from src.corpus_maker.normalizer import normalize_questions
        
        source = tmp_path / "source.json"
        source.write_text(json.dumps([
            {"query": "Q1?", "answer": "A1"},
            {"q": "Q2?", "a": "A2"},
            {"question": "Q3?", "expected": "A3"}
        ]))
        
        dest = tmp_path / "normalized.json"
        count = normalize_questions(source, dest)
        
        assert count == 3
        
        with open(dest) as f:
            result = json.load(f)
        
        assert result[0]["question"] == "Q1?"
        assert result[0]["expected"] == "A1"
        assert result[1]["question"] == "Q2?"
        assert result[1]["expected"] == "A2"
        assert result[2]["question"] == "Q3?"
        assert result[2]["expected"] == "A3"


class TestValidator:
    """Tests for document and question validation."""
    
    def test_validates_question_count(self, tmp_path):
        from src.corpus_maker.validator import validate_questions
        
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"question": f"Q{i}?", "expected": f"A{i}"} for i in range(50)
        ]))
        
        errors = validate_questions(q_file, require_100=True)
        assert any("100 questions" in e for e in errors)
    
    def test_validates_required_fields(self, tmp_path):
        from src.corpus_maker.validator import validate_questions
        
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"question": "Q1?"}
        ] * 100))
        
        errors = validate_questions(q_file)
        assert any("expected" in e.lower() for e in errors)
    
    def test_validates_missing_question_field(self, tmp_path):
        from src.corpus_maker.validator import validate_questions
        
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"expected": "A1"}
        ] * 100))
        
        errors = validate_questions(q_file)
        assert any("question" in e.lower() for e in errors)
    
    def test_accepts_valid_questions(self, tmp_path):
        from src.corpus_maker.validator import validate_questions
        
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"id": i, "question": f"Q{i}?", "expected": f"A{i}"} 
            for i in range(1, 101)
        ]))
        
        errors = validate_questions(q_file)
        assert len(errors) == 0
    
    def test_validates_document_folder_exists(self, tmp_path):
        from src.corpus_maker.validator import validate_documents
        
        errors = validate_documents(tmp_path / "nonexistent")
        assert any("not found" in e for e in errors)
    
    def test_validates_document_folder_has_files(self, tmp_path):
        from src.corpus_maker.validator import validate_documents
        
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        errors = validate_documents(empty_dir)
        assert any("No supported documents" in e for e in errors)
    
    def test_accepts_valid_documents(self, tmp_path):
        from src.corpus_maker.validator import validate_documents
        
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "test.pdf").write_bytes(b"%PDF-1.4")
        (docs_dir / "test.docx").write_bytes(b"PK")
        
        errors = validate_documents(docs_dir)
        assert len(errors) == 0
    
    def test_list_valid_documents(self, tmp_path):
        from src.corpus_maker.validator import list_valid_documents
        
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "test.pdf").write_bytes(b"%PDF-1.4")
        (docs_dir / "test.txt").write_text("hello")
        (docs_dir / ".hidden").write_text("hidden")
        (docs_dir / "readme.md").write_text("readme")
        
        valid = list_valid_documents(docs_dir)
        
        assert len(valid) == 2
        filenames = [f.name for f in valid]
        assert "test.pdf" in filenames
        assert "test.txt" in filenames
        assert ".hidden" not in filenames
        assert "readme.md" not in filenames


class TestManifest:
    """Tests for manifest generation."""
    
    def test_computes_sha256(self, tmp_path):
        from src.corpus_maker.manifest import compute_sha256
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        hash1 = compute_sha256(test_file)
        hash2 = compute_sha256(test_file)
        
        assert hash1 == hash2
        assert len(hash1) == 64
    
    def test_generates_manifest(self, tmp_path):
        from src.corpus_maker.manifest import generate_manifest, compute_sha256
        
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"id": i, "question": f"Q{i}?", "expected": f"A{i}"}
            for i in range(1, 101)
        ]))
        
        documents = [
            {
                "source_path": "/source/doc1.pdf",
                "dest_path": "documents/strategy/doc1.pdf",
                "sha256": "abc123",
                "size_bytes": 1024
            }
        ]
        
        manifest = generate_manifest(
            corpus_name="Test Corpus",
            documents=documents,
            question_file=q_file,
            user="test_user",
            anchor_org="Test Org"
        )
        
        assert manifest["corpus_name"] == "Test Corpus"
        assert manifest["anchor_organization"] == "Test Org"
        assert manifest["created_by"] == "test_user"
        assert len(manifest["documents"]) == 1
        assert manifest["summary"]["total_documents"] == 1
        assert manifest["summary"]["total_questions"] == 100


class TestRegistry:
    """Tests for corpus registration."""
    
    def test_register_and_get_corpus(self, tmp_path, monkeypatch):
        import src.corpus_maker.registry as registry
        
        test_config = tmp_path / "test_config.json"
        monkeypatch.setattr(registry, 'TEST_CONFIG_PATH', test_config)
        
        result = registry.register_corpus(
            corpus_name="Test Corpus",
            vault_id="test-vault-123",
            questions_file="test_100q.json",
            anchor_org="Test Org",
            document_count=50,
            question_count=100
        )
        
        assert result is True
        
        config = registry.get_corpus_config("Test Corpus")
        assert config is not None
        assert config["vault_id"] == "test-vault-123"
        assert config["anchor_org"] == "Test Org"
        assert config["document_count"] == 50
    
    def test_list_corpora(self, tmp_path, monkeypatch):
        import src.corpus_maker.registry as registry
        
        test_config = tmp_path / "test_config.json"
        monkeypatch.setattr(registry, 'TEST_CONFIG_PATH', test_config)
        
        registry.register_corpus("Corpus A", "vault-a", "a.json", "Org A")
        registry.register_corpus("Corpus B", "vault-b", "b.json", "Org B")
        
        corpora = registry.list_corpora()
        
        assert "Corpus A" in corpora
        assert "Corpus B" in corpora
    
    def test_unregister_corpus(self, tmp_path, monkeypatch):
        import src.corpus_maker.registry as registry
        
        test_config = tmp_path / "test_config.json"
        monkeypatch.setattr(registry, 'TEST_CONFIG_PATH', test_config)
        
        registry.register_corpus("Test Corpus", "vault-123", "test.json", "Test Org")
        
        result = registry.unregister_corpus("Test Corpus")
        assert result is True
        
        config = registry.get_corpus_config("Test Corpus")
        assert config is None


class TestCLIParsing:
    """Tests for CLI argument parsing."""
    
    def test_parse_folder_mapping_with_category(self):
        from src.corpus_maker.cli import parse_folder_mapping
        
        mapping = parse_folder_mapping("/path/to/docs:strategy")
        assert str(mapping.source_path) == "/path/to/docs"
        assert mapping.category == "strategy"
    
    def test_parse_folder_mapping_without_category(self):
        from src.corpus_maker.cli import parse_folder_mapping
        
        mapping = parse_folder_mapping("/path/to/docs")
        assert str(mapping.source_path) == "/path/to/docs"
        assert mapping.category == "uncategorized"
