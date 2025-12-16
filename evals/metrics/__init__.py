"""Metrics for evals."""

import os

metrics = []

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

for file in os.listdir(PROMPTS_DIR):
    if file.endswith(".md"):
        metrics.append({"name": file.replace(".md", ""), "prompt": open(os.path.join(PROMPTS_DIR, file), "r").read()})
