import unittest
from unittest.mock import patch

import llm_client


class LLMClientTests(unittest.TestCase):
    def test_responses_5xx_falls_back_to_chat_completions(self):
        temporary_error = llm_client.LLMRequestError(
            "Model service returned HTTP 500",
            status_code=500,
        )

        with (
            patch.object(llm_client, "API_STYLE", "responses"),
            patch.object(
                llm_client,
                "_responses_request",
                side_effect=temporary_error,
            ) as responses_request,
            patch.object(
                llm_client,
                "_chat_completions_request",
                return_value="fallback worked",
            ) as chat_request,
        ):
            result = llm_client._create_response(
                "instructions",
                "question",
                max_tokens=800,
            )

        self.assertEqual(result, "fallback worked")
        responses_request.assert_called_once()
        chat_request.assert_called_once_with(
            "instructions",
            "question",
            None,
            1_200,
        )

    def test_authentication_error_does_not_fall_back(self):
        auth_error = llm_client.LLMRequestError(
            "Model service returned HTTP 401",
            status_code=401,
        )

        with (
            patch.object(llm_client, "API_STYLE", "responses"),
            patch.object(
                llm_client,
                "_responses_request",
                side_effect=auth_error,
            ),
            patch.object(llm_client, "_chat_completions_request") as chat_request,
        ):
            with self.assertRaises(llm_client.LLMRequestError):
                llm_client._create_response("instructions", "question")

        chat_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
