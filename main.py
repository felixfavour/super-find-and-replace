import os
import re
from pathlib import Path
from typing import List, Tuple, Dict

def extract_filename_from_path(svg_path: str) -> str:
    """Extract filename from SVG path and convert to PascalCase with Icon suffix"""
    # Remove leading slash and get filename without extension
    filename = Path(svg_path.lstrip('/')).stem
    
    # Convert kebab-case or snake_case to PascalCase
    words = re.split(r'[-_]', filename)
    pascal_case = ''.join(word.capitalize() for word in words)

    # If the filename ends with Icon already, return it as-is
    if pascal_case.endswith('Icon'):
        return pascal_case
    
    return f"{pascal_case}Icon"

def parse_img_tag(img_tag: str) -> Dict[str, str]:
    """Parse img tag to extract src and other attributes"""
    # Extract src attribute
    src_match = re.search(r'src="([^"]*)"', img_tag)
    src = src_match.group(1) if src_match else ""
    
    # Extract all attributes except src, @click and v-svg-inline
    # Also remove :class attributes as it is registered as a directive
    temp_img_tag = img_tag.replace(':class=', 'dynamic-class=').replace(':stye=', 'dynamic-style=')
    # print('temp_img_tag', temp_img_tag)
    attributes = {}
    attr_pattern = r'(\w+(?:-\w+)*)="([^"]*)"'
    # print('img-tag', img_tag)
    for match in re.finditer(attr_pattern, temp_img_tag):
        attr_name, attr_value = match.groups()
        # print('attr_name', attr_name)
        if attr_name not in ['src', 'v-svg-inline', 'click', 'dynamic-class', 'dynamic-style', 'v-if', 'v-else-if', 'v-else', 'v-for']:
            attributes[attr_name] = attr_value
    
    # Extract vue directives (attributes starting with v- or @)
    vue_directives = {}
    directive_pattern = r'((?:v-|@|:)\w+(?:[.-]\w+)*)(?:="([^"]*)")?'
    for match in re.finditer(directive_pattern, img_tag):
        directive_name, directive_value = match.groups()
        if directive_name != 'v-svg-inline':
            vue_directives[directive_name] = directive_value or ''
    
    return {
        'src': src,
        'attributes': attributes,
        'vue_directives': vue_directives
    }

def find_script_tag_position(content: str) -> Tuple[int, int]:
    """Find the position to insert import statements in script tag"""
    script_match = re.search(r'<script[^>]*>', content)
    if not script_match:
        return -1, -1
    
    script_start = script_match.end()
    
    # Look for existing imports to insert after them
    existing_imports = re.finditer(r'^import\s+.*?$', content[script_start:], re.MULTILINE)
    last_import_end = script_start
    
    for import_match in existing_imports:
        last_import_end = script_start + import_match.end()
    
    return script_start, last_import_end

def process_vue_file(file_path: str) -> bool:
    """Process a single Vue file and return True if changes were made"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        imports_to_add = []
        replacements = []
        skipped_img_tags = []
        
        # Find all img tags with v-svg-inline attribute
        img_pattern = r'<img[^>]*v-svg-inline[^>]*/?>'
        
        for match in re.finditer(img_pattern, content):
            img_tag = match.group(0)

            # Skip img tags with dynamic src attribute
            if ":src" in img_tag:
              skipped_img_tags.append(img_tag)
              continue
            
            parsed = parse_img_tag(img_tag)

            # print('parsed', img_tag, parsed, "\n")
            
            if not parsed['src']:
                continue
                
            # Generate component name
            component_name = extract_filename_from_path(parsed['src'])
            
            # Create import statement
            import_statement = f"import {component_name} from '~/public{parsed['src']}'"
            if import_statement not in imports_to_add:
                imports_to_add.append(import_statement)
            
            # Build replacement component
            replacement_parts = [f"<{component_name}"]
            
            # Add regular attributes
            for attr_name, attr_value in parsed['attributes'].items():
                # print('parsed', parsed)
                # print('parsed-attributes', parsed['attributes'])
                replacement_parts.append(f' {attr_name}="{attr_value}"')
            
            # Add Vue directives
            for directive_name, directive_value in parsed['vue_directives'].items():
                if directive_value:
                    replacement_parts.append(f' {directive_name}="{directive_value}"')
                else:
                    replacement_parts.append(f' {directive_name}')
            
            replacement_parts.append(' />')
            replacement_component = ''.join(replacement_parts)
            
            replacements.append((img_tag, replacement_component))
        
        if not imports_to_add:
            return False  # No changes needed
        
        # Add imports to script tag
        script_start, last_import_end = find_script_tag_position(content)
        
        if script_start == -1:
            print(f"Warning: No script tag found in {file_path}")
            return False
        
        # Insert imports
        import_text = '\n' + '\n'.join(imports_to_add) + '\n'
        
        if last_import_end > script_start:
            # Insert after existing imports
            content = content[:last_import_end] + import_text + content[last_import_end:]
        else:
            # Insert at beginning of script tag
            content = content[:script_start] + import_text + content[script_start:]
        
        # Replace img tags with components
        for old_tag, new_component in replacements:
            content = content.replace(old_tag, new_component)
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Processed: {file_path}")
        print(f"  - Added {len(imports_to_add)} imports")
        print(f"  - Replaced {len(replacements)} img tags")
        print(f"  - Skipped {len(skipped_img_tags)} img tags with dynamic src attribute")
        
        return True
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def find_vue_files(directory: str) -> List[str]:
    """Recursively find all .vue files in directory"""
    vue_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.vue'):
                vue_files.append(os.path.join(root, file))
    return vue_files

def main():
    """Main function to process all Vue files"""
    # Get directory to process (current directory by default)
    directory = input("Enter directory path (or press Enter for current directory): ").strip()
    if not directory:
        directory = "."
    
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist!")
        return
    
    # Find all Vue files
    vue_files = find_vue_files(directory)
    
    if not vue_files:
        print("No .vue files found in the specified directory.")
        return
    
    print(f"Found {len(vue_files)} .vue files")
    
    # Ask for confirmation
    proceed = input("Do you want to proceed with the transformation? (y/N): ").strip().lower()
    if proceed != 'y':
        print("Transformation cancelled.")
        return
    
    # Process each file
    processed_count = 0
    print(vue_files)
    for vue_file in vue_files:
        if process_vue_file(vue_file):
            processed_count += 1
    
    print(f"\nTransformation complete!")
    print(f"Processed {processed_count} out of {len(vue_files)} files")

if __name__ == "__main__":
    main()
