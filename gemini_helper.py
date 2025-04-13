import os
import sys
import subprocess
import json
import argparse
import readline
from google import genai
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich import print
from typing import Dict, Any

console = Console()

# Configure API key
def setup_api():
    """Set up the Gemini API with the API key from environment or prompt user."""
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        console.print("[yellow]Gemini API key not found in environment variables.[/yellow]")
        api_key = input("Please enter your Gemini API key: ").strip()
        # Save to environment for current session
        os.environ["GEMINI_API_KEY"] = api_key
        
        # Ask if user wants to save to .bashrc or .zshrc
        save = input("Do you want to save this API key to your shell profile? (y/n): ").lower()
        if save == 'y':
            shell = os.environ.get("SHELL", "")
            if "zsh" in shell:
                profile = os.path.expanduser("~/.zshrc")
            else:
                profile = os.path.expanduser("~/.bashrc")
            
            with open(profile, "a") as f:
                f.write(f'\nexport GEMINI_API_KEY="{api_key}"\n')
            console.print(f"[green]API key saved to {profile}[/green]")
    
    return api_key

def generate_command(query: str, client) -> Dict[str, Any]:
    """
    Generate a terminal command from a natural language query using Gemini.
    Returns a structured response with command, explanation, and safety assessment.
    """
    prompt = f"""
    You are a macOS terminal assistant. I need you to interpret this natural language query into an appropriate terminal command:
    
    "{query}"
    
    Please provide:
    1. The most suitable terminal command for the request
    2. A clear explanation of what the command does
    3. A safety assessment (is this command safe to run?)
    
    Format your response as a valid JSON object with these fields:
    {{
        "command": "the terminal command",
        "explanation": "explanation of what the command does",
        "safe": true/false,
        "warning": "warning message if command is potentially destructive" (optional)
    }}
    
    Only respond with this JSON format and nothing else. Do not include markdown code blocks or any other text.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        # Extract JSON from response
        response_text = response.text.strip()
        # Handle potential JSON formatting issues
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON if it's wrapped in code blocks or has extra text
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                raise Exception("Could not parse JSON response")
        
        return result
    except Exception as e:
        console.print(f"[red]Error generating command: {str(e)}[/red]")
        return {
            "command": "",
            "explanation": f"Failed to process request: {str(e)}",
            "safe": False,
            "warning": "Unable to generate a proper response"
        }

def execute_command(command: str) -> str:
    """Execute the shell command and return the output."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            text=True, 
            capture_output=True
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error (code {result.returncode}):\n{result.stderr}"
    except Exception as e:
        return f"Failed to execute command: {str(e)}"

def main():
    """Main function to run the AI terminal assistant."""
    parser = argparse.ArgumentParser(description="AI Terminal Assistant")
    parser.add_argument("query", nargs="*", help="Natural language query for the terminal")
    args = parser.parse_args()
    
    # Display welcome message if no query provided
    if not args.query:
        console.print(Panel.fit(
            "[bold green]AI Terminal Assistant[/bold green]\n"
            "Ask me anything about terminal commands in plain English.\n"
            "Type [bold]exit[/bold] or [bold]quit[/bold] to close the assistant.",
            title="Welcome",
            border_style="green"
        ))
    
    # Setup the API key and client
    api_key = setup_api()
    client = genai.Client(api_key=api_key)
    
    # Interactive mode if no command-line query
    if not args.query:
        while True:
            try:
                query = input("\n[?] What would you like to do? > ")
                if query.lower() in ["exit", "quit", "q"]:
                    console.print("[green]Goodbye![/green]")
                    break
                
                if not query.strip():
                    continue
                
                process_query(query, client)
            except KeyboardInterrupt:
                console.print("\n[green]Goodbye![/green]")
                break
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
    else:
        # Process the command-line query
        query = " ".join(args.query)
        process_query(query, client)

def process_query(query: str, client):
    """Process a user query and handle the result."""
    console.print(f"\n[blue]Processing: [bold]{query}[/bold][/blue]")
    
    with console.status("[bold green]Thinking...[/bold green]"):
        result = generate_command(query, client)
    
    if not result.get("command"):
        console.print("[red]Sorry, I couldn't generate a command for that query.[/red]")
        return
    
    # Display the command
    console.print("\n[bold]Suggested Command:[/bold]")
    print(Panel(result["command"], border_style="cyan"))
    
    # Display the explanation
    console.print("\n[bold]Explanation:[/bold]")
    console.print(Markdown(result["explanation"]))
    
    # Display safety warning if needed
    if not result.get("safe", True):
        console.print("\n[bold red]⚠️ Safety Warning:[/bold red]")
        warning = result.get("warning", "This command might be destructive or have unintended consequences.")
        console.print(Panel(warning, border_style="red"))
    
    # Ask for confirmation
    confirm = input("\nDo you want to execute this command? (y/n): ").lower()
    if confirm == 'y':
        console.print("\n[bold]Executing command...[/bold]")
        output = execute_command(result["command"])
        
        console.print("\n[bold]Output:[/bold]")
        if output.strip():
            print(Panel(output, border_style="green"))
        else:
            console.print("[dim]Command executed successfully with no output.[/dim]")
    else:
        console.print("[yellow]Command execution cancelled.[/yellow]")

if __name__ == "__main__":
    main()