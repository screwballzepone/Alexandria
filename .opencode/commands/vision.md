# /vision — Analyze an image using a vision-capable AI model

## Usage
```
/vision <file_path>
```

## Description
Sends an image file to GPT-4o-mini (multimodal) for analysis. The model will describe what it sees — plots, screenshots, UI mockups, diagrams, etc.

## Template
When this command is invoked:
1. Extract the file path argument (relative or absolute)
2. If the path is relative, resolve it against the workspace root
3. Verify the file exists and is an image (.png, .jpg, .jpeg, .gif, .bmp)
4. Run: `opencode.cmd run "Analyze this image in detail. Describe what you see." --file <resolved_path> --model openrouter/openai/gpt-4o-mini --dangerously-skip-permissions`
5. Capture the output and report it to the user

## Error handling
- If no file path provided: "Usage: /vision <file_path>"
- If file doesn't exist: "File not found: <path>"
- If file is not an image: "Not a supported image format. Use .png, .jpg, .jpeg, .gif, or .bmp"
- If opencode.cmd fails: report the error message
