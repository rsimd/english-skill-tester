"""Integration tests for CEFR-based features across models, storage, prompt engine, and metrics."""

from english_skill_tester.assessment.metrics import (
    categorize_error_patterns,
    compute_cefr_vocabulary_distribution,
)
from english_skill_tester.conversation.prompt_engine import PromptEngine
from english_skill_tester.models.session import SkillLevel
from english_skill_tester.models.user_profile import UserProfile


class TestUserProfileToPromptEngineFlow:
    def test_user_profile_to_prompt_engine_flow(self):
        profile = UserProfile(
            user_id="test-integration-user",
            estimated_cefr="B1",
            weak_grammar_points=["article", "tense"],
        )
        engine = PromptEngine()
        prompt = engine.build_prompt(cefr="B1", user_profile=profile)

        assert prompt, "PromptEngine should return non-empty prompt"
        assert len(prompt) > 0


class TestSkillLevelCefrMapping:
    def test_skill_level_cefr_mapping(self):
        expected = {
            SkillLevel.BEGINNER: "A1",
            SkillLevel.ELEMENTARY: "A2",
            SkillLevel.INTERMEDIATE: "B1",
            SkillLevel.UPPER_INTERMEDIATE: "B2",
            SkillLevel.ADVANCED: "C1",
        }
        for level, expected_cefr in expected.items():
            assert level.cefr == expected_cefr, (
                f"SkillLevel.{level.name}.cefr should be {expected_cefr}, got {level.cefr}"
            )


class TestPromptEngineLoadsAllYaml:
    def test_prompt_engine_loads_all_yaml(self):
        engine = PromptEngine()
        cefr_levels = ["A1", "A2", "B1", "B2", "C1"]
        for cefr in cefr_levels:
            prompt = engine.build_prompt(cefr=cefr)
            assert prompt, f"PromptEngine should return non-empty prompt for CEFR level {cefr}"


class TestCefrVocabularyDistribution:
    def test_cefr_vocabulary_distribution(self):
        text = "I went to the store and bought some bread and milk for my family."
        result = compute_cefr_vocabulary_distribution(text)

        assert "A1_A2" in result, "Result should contain 'A1_A2' key"
        assert "B1_B2" in result, "Result should contain 'B1_B2' key"
        assert "C1_plus" in result, "Result should contain 'C1_plus' key"

        total = result["A1_A2"] + result["B1_B2"] + result["C1_plus"]
        assert 0.0 <= total <= 1.001, f"Sum of distribution values should be in [0, 1], got {total}"


class TestCategorizeErrorPatterns:
    def test_categorize_error_patterns(self):
        errors = [
            {"type": "tense_error", "text": "He go to school", "correction": "He goes to school"},
            {"type": "article_omission", "text": "I have dog", "correction": "I have a dog"},
            {"type": "tense_error", "text": "She go yesterday", "correction": "She went yesterday"},
        ]
        result = categorize_error_patterns(errors)

        assert isinstance(result, dict), "Result should be a dict"
        assert "tense_error" in result, "Result should contain 'tense_error'"
        assert result["tense_error"] == 2, f"Expected 2 tense_error, got {result['tense_error']}"
        assert "article_omission" in result, "Result should contain 'article_omission'"
        assert result["article_omission"] == 1


class TestUserProfilePersistence:
    def test_user_profile_persistence(self, tmp_path, monkeypatch):
        """UserProfile の保存とロードで値が正しく復元されることを検証"""
        import english_skill_tester.storage.user_profile as storage_mod

        def mock_get_profile_path(user_id: str):
            return tmp_path / f"{user_id}.json"

        monkeypatch.setattr(storage_mod, "get_profile_path", mock_get_profile_path)

        profile = UserProfile(
            user_id="persist-test-user",
            estimated_cefr="B2",
            weak_grammar_points=["preposition", "article"],
        )
        storage_mod.save_profile(profile)

        loaded = storage_mod.load_profile("persist-test-user")
        assert loaded.estimated_cefr == "B2", (
            f"estimated_cefr should be 'B2', got {loaded.estimated_cefr}"
        )
        assert loaded.weak_grammar_points == ["preposition", "article"], (
            f"weak_grammar_points mismatch: {loaded.weak_grammar_points}"
        )
