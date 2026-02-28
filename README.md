
# Arduino Code Translator Bot

A terminal-based bot that translates natural language descriptions into Arduino code using OpenAI's API.

## Setup

1. Create and activate a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your OpenAI API key. You have two options:

   **Option A: Environment variable (recommended)**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

   **Option B: Create a .api_key file**
   ```bash
   echo "your-api-key-here" > .api_key
   ```

   Note: The `.api_key` file is gitignored for security.

## Usage

**Note:** All generated Arduino code is automatically saved to the `arduino_code/` folder by default!

### Quick Start (using helper script)
```bash
./run.sh "Blink an LED on pin 13"
```
The code will be saved to `arduino_code/blink_an_led_on_pin_13_TIMESTAMP.ino`

### Single translation
```bash
# Make sure virtual environment is activated
source venv/bin/activate
python arduino_translator.py "Blink an LED on pin 13"
```

### Interactive mode
```bash
python arduino_translator.py -i
```
Each generated code will be saved to a separate file in `arduino_code/`

### Customize output directory
```bash
python arduino_translator.py "Read temperature sensor" -d my_projects
```

### Save to specific file (overrides auto-save)
```bash
python arduino_translator.py "Read temperature sensor" -o custom_name.ino
```

### Don't save automatically (only print)
```bash
python arduino_translator.py "Blink LED" --no-save
```

### Pipe input
```bash
echo "Control servo with potentiometer" | python arduino_translator.py
```

### Use different model
```bash
python arduino_translator.py "Your description" -m gpt-4o
```

## Examples

```bash
# Simple LED blink
python arduino_translator.py "Blink an LED on pin 13 every second"

# Sensor reading
python arduino_translator.py "Read temperature from DHT11 sensor on pin 2 and print to serial monitor"

# Motor control
python arduino_translator.py "Control a servo motor with a potentiometer, servo on pin 9, pot on A0"

# Multiple components
python arduino_translator.py "When button on pin 7 is pressed, turn on LED on pin 13 for 2 seconds"
```

## Features

- ✅ Natural language to Arduino code translation
- ✅ Interactive mode for multiple translations
- ✅ Save output directly to .ino files
- ✅ Supports piping from stdin
- ✅ Configurable OpenAI model
- ✅ Secure API key handling
>>>>>>> d07cbba (Initial commit for CursorBot)
