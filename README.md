# LibreOffice Translator

AI-powered document translation extension for LibreOffice Writer.

## Features

- **Translate Selected Text** (Ctrl+T) - Translate highlighted text instantly
- **Translate Entire Document** (Ctrl+Shift+T) - Translate whole document paragraph by paragraph
- **Auto Language Detection** - Automatically detects Chinese/English and translates in the correct direction
- **Preserve Original** - Keeps original text intact, inserts translation below
- **Local AI** - Uses local AI models via LM Studio or Ollama, no cloud required

## Requirements

- LibreOffice Writer (7.0+)
- **LM Studio** (http://127.0.0.1:1234) or **Ollama** (http://127.0.0.1:11434)
- Compatible AI model (e.g., Qwen, Gemma, translategemma)

## Installation

### Option 1: Pre-built Extension

1. Download the latest `.oxt` file from [Releases](https://github.com/lazycat710/libreoffice-translator/releases)
2. Open LibreOffice → Tools → Extension Manager
3. Click **Add** → Select the `.oxt` file
4. Restart LibreOffice

### Option 2: Build from Source

```bash
git clone https://github.com/lazycat710/libreoffice-translator.git
cd libreoffice-translator
chmod +x build.sh
./build.sh
```

This will generate `Translator.oxt` in the project root.

## Configuration

1. Go to **Translator → Settings** menu
2. Set the API endpoint:
   - **LM Studio**: `http://127.0.0.1:1234`
   - **Ollama**: `http://127.0.0.1:11434`
3. Enter your model name (e.g., `qwen2.5-coder:14b` or `translategemma-4b-it`)
4. Click OK

## Supported Models

| Model | API | Notes |
|-------|-----|-------|
| Qwen series | Chat | Standard OpenAI format |
| Gemma series | Completions/Chat | Works with LM Studio |
| translategemma | Completions | Optimized translation model |

## Usage

1. Open a document in LibreOffice Writer
2. **Translate Selection**: Select text → Menu: Translator → Translate Selection (or Ctrl+T)
3. **Translate Document**: Menu: Translator → Translate Entire Document (or Ctrl+Shift+T)
4. Translations will be inserted below the original text

## Development

### Project Structure

```
libreoffice-translator/
├── main.py                 # Main extension code
├── Addons.xcu             # Menu configuration
├── Accelerators.xcu        # Keyboard shortcuts
├── description.xml         # Extension metadata
├── META-INF/              # Extension manifest
│   └── manifest.xml
├── registration/           # License files
│   └── license.txt
└── assets/                # Icons
    └── logo.png
```

### Building

The extension uses Python UNO API for LibreOffice integration.

## License

MPL 2.0 - See [LICENSE](LICENSE) for details.

## Contributing

Issues and Pull Requests are welcome!
