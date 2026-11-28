---
description: Explain a file as interview or demo preparation
argument-hint: <file>
---
File to explain: $ARGUMENTS

If no file is given, ask which one. If it does not exist, say so. Never open an env
file that holds secrets.

Read the file (and only what you need to understand it, such as the `contracts/` models
it uses or the `data/policies/*.yaml` values it reads), then explain it as if I will be
questioned on it in an interview or hackathon demo:
1. Purpose, where it fits in the pipeline, and which member owns it
2. Key functions or sections
3. Design choices, why they were made, and their trade-offs
4. One likely judge or interview question, with a strong answer

Be concise. Base every claim on the code, and say when a reason is your inference.
Do not edit files.
