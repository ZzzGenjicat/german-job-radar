"""Small, inspectable terminology map; exact JD evidence is still required."""
import re

# Related search terms, not claims about the applicant's skills.
GROUPS = (
    ('AI', 'KI', 'Künstliche Intelligenz', 'Artificial Intelligence', 'LLM', 'RAG', 'AI Agent', 'KI Agent', 'Agentic AI', 'GenAI', 'Generative AI', 'Machine Learning'),
    ('CRM', 'Customer Relationship Management', 'Salesforce', 'HubSpot', 'Lead Management', 'Lead Scoring'),
    ('Automatisierung', 'Automation', 'Prozessautomatisierung', 'Workflow', 'Digitalisierung', 'Prozessoptimierung'),
    ('Vertrieb', 'Sales', 'Business Development', 'Account Management', 'Revenue Operations'),
    ('Softwareentwicklung', 'Software Engineering', 'Software Engineer', 'Backend', 'Frontend', 'Python', 'Java', 'React', 'TypeScript'),
    ('Buchhaltung', 'Finanzbuchhaltung', 'Accounting', 'Rechnungswesen', 'Accounts Payable', 'Accounts Receivable'),
    ('Personal', 'Human Resources', 'Recruiting', 'Talent Acquisition', 'People Operations'),
    ('Projektmanagement', 'Project Management', 'Project Manager', 'Projektmanager', 'PMO'),
    ('Logistik', 'Logistics', 'Supply Chain', 'Disposition', 'Lagerlogistik'),
)


def find_term(text, term):
    pattern = re.escape(term).replace(r'\ ', r'[\s\-]+')
    # German compounds are common. Short abbreviations must be separate words.
    if len(term) <= 4:
        pattern = r'(?<!\w)' + pattern + r'(?!\w)'
    match = re.search(pattern, text, re.I)
    return text[max(0, match.start()-45):match.end()+100].strip() if match else ''


def related_groups(seeds):
    text = ' '.join(seeds)
    return [group for group in GROUPS if any(find_term(text, term) for term in group)]


def theme_matches(text, theme):
    hit = find_term(text, theme)
    if hit:
        return hit
    # Synonyms only apply when a theme is a known broad concept, not a stack
    # requirement: a Python target must not become any Java job.
    group = next((g for g in GROUPS if theme.casefold() in {x.casefold() for x in g[:4]}), None)
    if group:
        for term in group:
            hit = find_term(text, term)
            if hit:
                return hit
    return ''
