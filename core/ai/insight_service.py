# core/ai/insight_service.py
from __future__ import annotations

import math
from typing import List, Optional
from core.llm.ollama_client import OllamaClient
from core.llm import prompt_templates as pt


class InsightService:
    """
    Summarize extracted logs (TXT/JSON) with a map-reduce strategy.

    Strategy:
      - If fits in one go -> single pass technical summary (timeline + anomalies + RCA).
      - Else -> split into chunks -> summarize each -> synthesize final technical summary.
    """

    def __init__(
        self,
        model: str = "llama3:latest",
        base_url: str = "http://localhost:11434",
        ctx_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        self.model = model
        self.client = OllamaClient(base_url=base_url, timeout=120)
        self.ctx_tokens = ctx_tokens
        self.temperature = temperature

        # Heuristic: ~4 chars/token; leave margin for prompts/system text.
        # Reserve ~1200 tokens for instructions -> ~4800 chars
        # So usable per request ~ (ctx_tokens - 1200) * 4
        usable_tokens = max(512, self.ctx_tokens - 1200)
        self.usable_chars_per_request = int(usable_tokens * 4)

        # For chunking we keep chunks smaller to allow model headroom
        self.chunk_chars = max(4000, int(self.usable_chars_per_request * 0.8))

    # ---------------- public API ----------------

    def summarize_text(self, extracted_text: str) -> str:
        if not extracted_text or not extracted_text.strip():
            return "No extracted content provided."

        text = extracted_text.strip()

        if len(text) <= self.usable_chars_per_request:
            return self._single_pass(text)

        chunks = self._split_text(text, self.chunk_chars)
        partials: List[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            partials.append(self._chunk_summary(chunk, idx, len(chunks)))

        stitched = "\n\n---\n".join(partials)
        return self._final_synthesis(stitched, len(chunks))

    # ---------------- internals ----------------

    def _single_pass(self, text: str) -> str:
        prompt = pt.TECHNICAL_INSIGHT_SINGLE.format(content=text)
        return self._call_llm(prompt)

    def _chunk_summary(self, chunk: str, i: int, n: int) -> str:
        prompt = pt.TECHNICAL_INSIGHT_CHUNK.format(index=i, total=n, content=chunk)
        return self._call_llm(prompt)

    def _final_synthesis(self, stitched_partials: str, n: int) -> str:
        prompt = pt.TECHNICAL_INSIGHT_FINAL.format(total=n, partials=stitched_partials)
        return self._call_llm(prompt)

    def _call_llm(self, prompt: str) -> str:
        # Deterministic, technical tone
        return self.client.generate(
            model=self.model,
            prompt=prompt,
            options={
                "temperature": self.temperature,
                "top_p": 0.9,
                "num_ctx": self.ctx_tokens,
            },
            keep_alive="5m",
        )

    @staticmethod
    def _split_text(text: str, chunk_chars: int) -> List[str]:
        """
        Split on double-newline boundaries when possible; fallback to hard cuts.
        """
        if len(text) <= chunk_chars:
            return [text]

        parts: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_chars)
            # try to break on \n\n within the window
            window = text[start:end]
            split_at = window.rfind("\n\n")
            if split_at == -1 or split_at < int(len(window) * 0.5):
                # no good boundary; take the window as-is
                parts.append(window)
                start = end
            else:
                cut = start + split_at
                parts.append(text[start:cut])
                start = cut + 2  # skip the \n\n
        return [p for p in parts if p.strip()]
