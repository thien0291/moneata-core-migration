#!/usr/bin/env python3
"""
Final PDF to Markdown converter with proper word spacing and formatting
"""

import pdfplumber
import re
import sys
import os

def extract_and_clean_text(pdf_path):
    """Extract text from PDF and clean it properly"""
    
    all_text = ""
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Processing {len(pdf.pages)} pages...")
            
            for i, page in enumerate(pdf.pages):
                print(f"Processing page {i+1}...")
                
                # Extract text from the page
                page_text = page.extract_text()
                
                if page_text:
                    all_text += page_text + "\n\n"
    
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""
    
    return all_text

def clean_and_structure_text(text):
    """Clean and structure the extracted text properly"""
    
    # First, let's split by double newlines to get potential paragraphs
    chunks = text.split('\n\n')
    
    structured_lines = []
    
    for chunk in chunks:
        if not chunk.strip():
            continue
            
        # Split by single newlines
        lines = chunk.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove page numbers
            if re.match(r'^\d+$', line):
                continue
                
            structured_lines.append(line)
    
    return structured_lines

def format_as_proper_markdown(lines):
    """Convert lines to properly formatted markdown"""
    
    markdown_content = []
    markdown_content.append("# ADR-015: Moneta Network Authentication and Identification")
    markdown_content.append("")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Skip the first few title repetitions
        if "ADR-015" in line and "Moneta Network Authentication" in line:
            i += 1
            continue
            
        # Status and Date
        if line.startswith("Status:"):
            markdown_content.append(f"**{line}**")
            markdown_content.append("")
            i += 1
            continue
            
        if line.startswith("Date:"):
            markdown_content.append(f"**{line}**")
            markdown_content.append("")
            i += 1
            continue
        
        # Main numbered sections
        if re.match(r'^(\d+)\.\s*(.+)', line):
            match = re.match(r'^(\d+)\.\s*(.+)', line)
            section_num = match.group(1)
            section_title = match.group(2)
            markdown_content.append(f"## {section_num}. {section_title}")
            markdown_content.append("")
            i += 1
            continue
        
        # Sub-sections (x.y format)
        if re.match(r'^(\d+\.\d+)\.\s*(.+)', line):
            match = re.match(r'^(\d+\.\d+)\.\s*(.+)', line)
            section_num = match.group(1)
            section_title = match.group(2)
            markdown_content.append(f"### {section_num}. {section_title}")
            markdown_content.append("")
            i += 1
            continue
        
        # Keywords that should be headers
        header_keywords = [
            "Current Challenges & Requirements:", "Goals:", "Use Cases:", "Narrative:",
            "Key Components of the Decision:", "Pros:", "Cons:", "Risks & Mitigations:",
            "Overall Solution:", "QR Code Authentication:", "OTP to mPass App Authentication:",
            "Human-Friendly Identifiers:", "Tier and Billing Management Security:",
            "Open Issues / Next Steps", "Story Definition"
        ]
        
        for keyword in header_keywords:
            if line.startswith(keyword):
                markdown_content.append(f"### {line}")
                markdown_content.append("")
                break
        else:
            # Check for technical labels
            if re.match(r'^[A-Z][a-zA-Z\s]+:$', line) and len(line) < 50:
                markdown_content.append(f"#### {line}")
                markdown_content.append("")
            
            # Check for list items
            elif (line.startswith("- ") or line.startswith("• ") or 
                  re.match(r'^\d+\.\s+', line) or
                  re.match(r'^[a-z]\.\s+', line)):
                markdown_content.append(line)
            
            # Check for sequence diagram content
            elif ("sequenceDiagram" in line or 
                  re.match(r'^\d+\s+(participant|alt|else|end)', line) or
                  "->" in line or "-->" in line):
                
                # Start collecting sequence diagram
                if "sequenceDiagram" in line:
                    markdown_content.append("```mermaid")
                
                markdown_content.append(line)
                
                # Look ahead to see if more sequence diagram content follows
                j = i + 1
                while j < len(lines) and (
                    "->" in lines[j] or "-->" in lines[j] or
                    re.match(r'^\d+\s+(participant|alt|else|end)', lines[j]) or
                    "Note over" in lines[j]
                ):
                    markdown_content.append(lines[j])
                    j += 1
                
                if "sequenceDiagram" in line:
                    markdown_content.append("```")
                    markdown_content.append("")
                
                i = j - 1
            
            # Regular paragraphs
            else:
                markdown_content.append(line)
                markdown_content.append("")
        
        i += 1
    
    return '\n'.join(markdown_content)

def manual_content_fixes(content):
    """Apply manual fixes for known content issues"""
    
    # Split large paragraphs and add proper structure
    fixes = [
        # Fix authentication section
        (r'Authentication: Design a secure OIDC-based.*?publisher groups\.',
         '''#### Authentication:
Design a secure OIDC-based passwordless authentication system managed by Moneta Core, using AWS Cognito, Lambda, DynamoDB, and API Gateway. Common flows involve users clicking a "Login with Moneta mPass" button on Publisher sites/apps, redirecting to Moneta Core's hosted UI, authenticating via their mPass mobile app (QR scan, OTP), and then being redirected back to the Publisher with OIDC tokens. The system must support session management, token revocation, refresh tokens, and SSO for publisher groups.'''),
        
        # Fix identification section
        (r'Identification: The current UUIDv4 identifiers.*?and security\.',
         '''#### Identification:
The current UUIDv4 identifiers for MOs, Publishers, and mPasses (MO UUID + User UUID) are not human-friendly. A new coding/alias scheme is needed, supporting global scale, high availability, performance, and security.'''),
        
        # Add more structure
        (r'Beyond the initial login, the system supports:',
         '''Beyond the initial login, the system supports:'''),
    ]
    
    for pattern, replacement in fixes:
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Clean up excessive whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content

def main():
    """Main conversion function"""
    
    pdf_file = "docs/adr/MoPrd-ADR-015_ Moneta Network Authentication and Identification-300625-052159.pdf"
    output_file = "docs/adr/ADR-015_MonetaNetworkAuthentication.md"
    
    if not os.path.exists(pdf_file):
        print(f"Error: PDF file not found: {pdf_file}")
        sys.exit(1)
    
    print("Extracting text from PDF...")
    raw_text = extract_and_clean_text(pdf_file)
    
    if not raw_text.strip():
        print("No content extracted from PDF.")
        sys.exit(1)
    
    print("Cleaning and structuring text...")
    lines = clean_and_structure_text(raw_text)
    
    print("Converting to markdown...")
    markdown_content = format_as_proper_markdown(lines)
    
    print("Applying manual fixes...")
    markdown_content = manual_content_fixes(markdown_content)
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"Successfully converted PDF to markdown: {output_file}")
    print(f"Output file size: {len(markdown_content)} characters")

if __name__ == "__main__":
    main() 