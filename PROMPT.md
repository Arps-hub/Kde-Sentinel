# Prompts Used for KDE Extraction

The extractor uses CIS recommendation headings as grounded KDE candidates, then applies the following prompt templates when logging or using Gemma-3-1B (`google/gemma-3-1b-it`) to identify requirements for a discovered KDE.

## zero-shot

```text
You are a security analyst. Read the following document excerpt and list all security requirements related to '{element_name}'.
Return only a numbered list of requirements. If none are found, return 'NONE'.

Document:
{document_text}

Requirements for '{element_name}':
```

## few-shot

```text
You are a security analyst extracting requirements from security documents.

Example 1:
Element: encryption
Document: 'All data at rest must be encrypted using AES-256. Data in transit must use TLS 1.2 or higher.'
Requirements:
1. Data at rest must be encrypted using AES-256.
2. Data in transit must use TLS 1.2 or higher.

Example 2:
Element: authentication
Document: 'Users must authenticate using multi-factor authentication. Passwords must be at least 12 characters.'
Requirements:
1. Users must authenticate using multi-factor authentication.
2. Passwords must be at least 12 characters.

Example 3:
Element: logging_and_monitoring
Document: 'All access to sensitive data must be logged.'
Requirements:
1. All access to sensitive data must be logged.

Now extract requirements for '{element_name}' from the following document:

Document:
{document_text}

Requirements for '{element_name}':
```

## chain-of-thought

```text
You are a security analyst. Use step-by-step reasoning to identify security requirements related to '{element_name}' in the document below.
Do not reveal hidden reasoning. Return only the final numbered requirements.

Step 1: Read the document carefully.
Step 2: Identify sentences or clauses that mention '{element_name}' or closely related concepts.
Step 3: Decide whether each sentence states an obligation, prohibition, or recommendation.
Step 4: Output only the final numbered requirements.
Step 5: If no requirements are found, write 'NONE'.

Document:
{document_text}

Requirements for '{element_name}':
```
