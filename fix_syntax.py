# Read the file and identify the problematic section
with open('c:\\Users\\ayant\\OneDrive\\Документы\\juldyz\\juldyz\\services\\scoring\\scoring_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Split by lines
lines = content.split('\n')

# Find the line with 'if __name__ == "__main__":'
if_main_index = None
for i, line in enumerate(lines):
    if 'if __name__ == "__main__":' in line:
        if_main_index = i
        break

if if_main_index is not None:
    # Keep everything up to the if __name__ block
    new_lines = lines[:if_main_index]
    
    # Add the corrected main block
    new_lines.append('if __name__ == "__main__":')
    new_lines.append('    try:')
    new_lines.append('        text = input("Вставь текст кандидата:\\n").strip()')
    new_lines.append('        result = evaluate_text(text)')
    new_lines.append('        print("\\n=== RESULT ===")')
    new_lines.append('        print(json.dumps(result, ensure_ascii=False, indent=2))')
    new_lines.append('    except Exception as exc:')
    new_lines.append('        print(f"Ошибка: {exc}")')
    
    # Write the corrected content
    with open('c:\\Users\\ayant\\OneDrive\\Документы\\juldyz\\juldyz\\services\\scoring\\scoring_engine.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    print("File fixed!")
else:
    print("Could not find if __name__ block")
