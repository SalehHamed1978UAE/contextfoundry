#!/usr/bin/env python3
"""Convert question bank markdown to JSON format."""

import re
import json
import sys
from pathlib import Path

def parse_question_bank(filepath: str) -> list:
    """Parse question bank markdown file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    pattern = r'\*\*Q(\d+):\*\*\s*(.+?)\n\*\*A\1:\*\*\s*(.+?)(?=\n\*\*(?:Q|Source)|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    questions = []
    for num, question, answer in matches:
        questions.append({
            "id": int(num),
            "question": question.strip(),
            "expected_answer": answer.strip().split('\n')[0].strip()
        })
    
    return questions

def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "test documents/Manus Healthtec/question_bank_200.md"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "test_questions/medsync_235q.json"
    
    questions = parse_question_bank(input_file)
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(questions, f, indent=2)
    
    print(f"Converted {len(questions)} questions to {output_file}")

if __name__ == '__main__':
    main()
