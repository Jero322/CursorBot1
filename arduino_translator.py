#!/usr/bin/env python3
"""
Arduino Code Translator Bot
Translates natural language descriptions to Arduino code using OpenAI API.
"""

import os
import sys
import argparse
import re
from datetime import datetime
from openai import OpenAI

# Initialize OpenAI client
def get_openai_client():
    """Initialize OpenAI client with API key from environment or provided key."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        # Try to read from a config file if it exists
        config_file = os.path.join(os.path.dirname(__file__), '.api_key')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                api_key = f.read().strip()
    
    if not api_key:
        print("Error: OpenAI API key not found.")
        print("Please set OPENAI_API_KEY environment variable or create a .api_key file")
        sys.exit(1)
    
    return OpenAI(api_key=api_key)

def generate_filename(description, output_dir="arduino_code"):
    """
    Generate a safe filename from the description.
    
    Args:
        description: Natural language description
        output_dir: Directory to save files in
    
    Returns:
        Full path to the output file
    """
    # Create output directory if it doesn't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, output_dir)
    os.makedirs(output_path, exist_ok=True)
    
    # Generate filename from description
    # Take first few words, sanitize, and limit length
    words = description.split()[:5]  # First 5 words
    filename = "_".join(words).lower()
    # Remove special characters, keep only alphanumeric and underscores
    filename = re.sub(r'[^a-z0-9_]', '', filename)
    # Limit length
    filename = filename[:40] if len(filename) > 40 else filename
    
    # Add timestamp if filename is too short or empty
    if not filename:
        filename = "arduino_code"
    
    # Add timestamp to ensure uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename}_{timestamp}.ino"
    
    return os.path.join(output_path, filename)

def save_code_to_file(code, description, output_dir="arduino_code", custom_output=None):
    """
    Save generated Arduino code to a file.
    
    Args:
        code: Generated Arduino code
        description: Original description (for filename generation)
        output_dir: Default directory to save files
        custom_output: Custom output path (overrides default)
    
    Returns:
        Path to the saved file
    """
    if custom_output:
        filepath = custom_output
    else:
        filepath = generate_filename(description, output_dir)
    
    with open(filepath, 'w') as f:
        f.write(code)
    
    return filepath

def translate_to_arduino(client, natural_language, model="gpt-4o-mini"):
    """
    Translate natural language to Arduino code.
    
    Args:
        client: OpenAI client instance
        natural_language: Natural language description
        model: OpenAI model to use
    
    Returns:
        Generated Arduino code
    """
    system_prompt = """You are an expert Arduino programmer writing code for an Adeept 4WD Smart Car Kit.

HARDWARE — use EXACTLY these pin numbers, no others:
  Motor A (right-side wheels): dirPin = 7,  pwmPin = 6
  Motor B (left-side  wheels): dirPin = 4,  pwmPin = 5
  Direction logic: LOW = forward, HIGH = backward
  Speed: analogWrite(pwmPin, 0..255)  — 200 is a good default speed

STANDARD MOVEMENT HELPERS to include at the top of every sketch:
  const int dirA = 7, pwmA = 6;   // right motors
  const int dirB = 4, pwmB = 5;   // left motors
  const int SPD = 200;             // default speed (0-255)

  void forward()  { digitalWrite(dirA,LOW);  analogWrite(pwmA,SPD); digitalWrite(dirB,LOW);  analogWrite(pwmB,SPD); }
  void backward() { digitalWrite(dirA,HIGH); analogWrite(pwmA,SPD); digitalWrite(dirB,HIGH); analogWrite(pwmB,SPD); }
  void turnRight(){ digitalWrite(dirA,HIGH); analogWrite(pwmA,SPD); digitalWrite(dirB,LOW);  analogWrite(pwmB,SPD); }
  void turnLeft() { digitalWrite(dirA,LOW);  analogWrite(pwmA,SPD); digitalWrite(dirB,HIGH); analogWrite(pwmB,SPD); }
  void stopAll()  { analogWrite(pwmA,0); analogWrite(pwmB,0); }

  // In setup(): pinMode(dirA,OUTPUT); pinMode(pwmA,OUTPUT); pinMode(dirB,OUTPUT); pinMode(pwmB,OUTPUT);

Guidelines:
1. Always provide complete, compilable Arduino code using the pin definitions above
2. Include the standard movement helpers and a setup() that configures all four pins as OUTPUT
3. Include a loop() with the requested logic
4. Add brief comments explaining what each section does
5. Use delay() for timed movements (e.g. delay(2000) = 2 seconds)
6. If the description is vague, make reasonable assumptions and document them in comments

Format your response as clean Arduino code without markdown code blocks (no ```arduino or ``` markers)."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": natural_language}
            ],
            temperature=0.3  # Lower temperature for more consistent code generation
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Translate natural language to Arduino code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python arduino_translator.py "Blink an LED on pin 13"
  python arduino_translator.py "Read temperature from DHT11 sensor and print to serial"
  python arduino_translator.py -i "Control a servo motor with a potentiometer"
  echo "Turn on LED when button is pressed" | python arduino_translator.py
        """
    )
    
    parser.add_argument(
        'description',
        nargs='?',
        help='Natural language description of what you want the Arduino to do'
    )
    
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Run in interactive mode (keep asking for descriptions)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Save output to a file (e.g., output.ino)'
    )
    
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='gpt-4o-mini',
        help='OpenAI model to use (default: gpt-4o-mini)'
    )
    
    parser.add_argument(
        '-d', '--output-dir',
        type=str,
        default='arduino_code',
        help='Directory to save generated Arduino files (default: arduino_code)'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not automatically save to file (only print to console)'
    )
    
    args = parser.parse_args()
    
    # Initialize OpenAI client
    client = get_openai_client()
    
    # Interactive mode
    if args.interactive:
        print("Arduino Code Translator Bot")
        print("=" * 50)
        print("Enter natural language descriptions to translate to Arduino code.")
        print("Type 'quit' or 'exit' to stop.\n")
        
        while True:
            try:
                description = input("Enter description: ").strip()
                
                if description.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if not description:
                    continue
                
                print("\nGenerating Arduino code...\n")
                code = translate_to_arduino(client, description, args.model)
                print(code)
                
                # Save to file automatically (unless --no-save is used)
                if not args.no_save:
                    filepath = save_code_to_file(code, description, args.output_dir, args.output)
                    print(f"\n✓ Code saved to: {filepath}")
                elif args.output:
                    # Only save if explicitly requested with -o flag
                    filepath = save_code_to_file(code, description, args.output_dir, args.output)
                    print(f"\n✓ Code saved to: {filepath}")
                
                print("\n" + "=" * 50 + "\n")
            
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break
    
    # Single description mode
    else:
        if args.description:
            description = args.description
        else:
            # Read from stdin if available
            if not sys.stdin.isatty():
                description = sys.stdin.read().strip()
            else:
                parser.print_help()
                sys.exit(1)
        
        if not description:
            print("Error: No description provided")
            sys.exit(1)
        
        print("Generating Arduino code...\n")
        code = translate_to_arduino(client, description, args.model)
        print(code)
        
        # Save to file automatically (unless --no-save is used)
        if not args.no_save:
            filepath = save_code_to_file(code, description, args.output_dir, args.output)
            print(f"\n✓ Code saved to: {filepath}")
        elif args.output:
            # Only save if explicitly requested with -o flag
            filepath = save_code_to_file(code, description, args.output_dir, args.output)
            print(f"\n✓ Code saved to: {filepath}")

if __name__ == '__main__':
    main()
