import os
from pathlib import Path
import questionary
from typing import Optional

def prompt_for_project_file(start_dir: str = ".", extension: str = ".json", prompt_text: str = "Select file") -> Optional[Path]:
    """
    Shows an interactive file picker using questionary to select a file.
    Navigates directories until a file with the given extension is selected.
    """
    current_dir = Path(start_dir).resolve()
    
    while True:
        try:
            items = []
            
            # Add parent directory option if not root
            if current_dir.parent != current_dir:
                items.append(questionary.Choice("🔙 [Back / Parent Directory]", value=".."))
                
            # List directories and target files
            for entry in sorted(os.listdir(current_dir)):
                full_path = current_dir / entry
                if full_path.is_dir() and not entry.startswith("."):
                    items.append(questionary.Choice(f"📁 {entry}/", value=full_path))
                elif full_path.is_file() and entry.endswith(extension):
                    items.append(questionary.Choice(f"📄 {entry}", value=full_path))
            
            if not items:
                items.append(questionary.Choice(f"❌ [No directories or {extension} files found here]", value="none"))
                
            choice = questionary.select(
                f"{prompt_text} (Current: {current_dir}):",
                choices=items,
                use_indicator=True
            ).ask()
            
            if choice is None:
                return None # Cancelled (Ctrl+C)
                
            if choice == "none":
                continue
                
            if choice == "..":
                current_dir = current_dir.parent
                continue
                
            path_choice = Path(choice)
            if path_choice.is_dir():
                current_dir = path_choice
            else:
                return path_choice
                
        except Exception as e:
            print(f"Error navigating: {e}")
            return None

def prompt_for_directory(start_dir: str = ".", prompt_text: str = "Select directory") -> Optional[Path]:
    """
    Shows an interactive directory picker using questionary.
    Navigates directories until the user chooses to select the current one.
    """
    current_dir = Path(start_dir).resolve()
    
    while True:
        try:
            items = []
            
            # Option to select current directory
            items.append(questionary.Choice(f"✅ [Select Current Directory: {current_dir.name}]", value="select_current"))
            
            # Add parent directory option if not root
            if current_dir.parent != current_dir:
                items.append(questionary.Choice("🔙 [Back / Parent Directory]", value=".."))
                
            # List directories
            for entry in sorted(os.listdir(current_dir)):
                full_path = current_dir / entry
                if full_path.is_dir() and not entry.startswith("."):
                    items.append(questionary.Choice(f"📁 {entry}/", value=full_path))
            
            choice = questionary.select(
                f"{prompt_text} (Current: {current_dir}):",
                choices=items,
                use_indicator=True
            ).ask()
            
            if choice is None:
                return None # Cancelled (Ctrl+C)
                
            if choice == "select_current":
                return current_dir
                
            if choice == "..":
                current_dir = current_dir.parent
                continue
                
            path_choice = Path(choice)
            if path_choice.is_dir():
                current_dir = path_choice
                
        except Exception as e:
            print(f"Error navigating: {e}")
            return None
