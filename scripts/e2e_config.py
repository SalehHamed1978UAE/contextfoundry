#!/usr/bin/env python3
"""
E2E Test Configuration

Defines vaults and queries to test. No hardcoding in the test script.
"""

VAULTS = [
    {
        "name": "TechVentures",
        "doc_dir": "test documents/TechVentures",
        "queries": [
            "Who is the CEO?",
            "What is the CEO's salary?",
            "Who is the CTO?",
            "Who is the CTO of TechVentures?",
            "What is Sarah Chen's compensation?",
            "Who reports to the CEO?",
            "What portfolio companies does TechVentures have?",
            "Tell me about CloudMatrix",
            "Tell me about HealthSync",
            "Tell me about SecureNode",
        ],
    },
    {
        "name": "Morrison & Sterling",
        "doc_dir": "test documents/Law Firm",
        "queries": [
            "Who is the Managing Partner?",
            "What is the Managing Partner's compensation?",
            "Who is the CFO?",
            "Who is the COO?",
            "Who reports to Amanda Foster?",
            "What practice groups does the firm have?",
            "Tell me about the litigation practice",
            "Who are the Tier 1 clients?",
            "What is Richard Sterling's compensation?",
        ],
    },
    {
        "name": "Riverside Medical Center",
        "doc_dir": "test documents/Hospital",
        "queries": [
            "Who is the CEO?",
            "What is the CEO's salary?",
            "Who is the CMO?",
            "Who is the CIO?",
            "What is the CIO's compensation?",
            "Who reports to the CEO?",
            "What departments does the hospital have?",
            "Tell me about the cardiac initiative",
            "Who leads the oncology department?",
            "Who leads the cardiology department?",
        ],
    },
    {
        "name": "Titan Manufacturing",
        "doc_dir": "test documents/Titan Manufacturing",
        "queries": [
            "Who is the CEO?",
            "What is the CEO's compensation?",
            "Who is the COO?",
            "Who is the CTO?",
            "Who reports to the CEO?",
            "Who manages the Detroit plant?",
            "What is the Detroit plant manager's compensation?",
            "What plants does the company have?",
            "Tell me about the automation initiative",
            "Who leads quality assurance?",
        ],
    },
    {
        "name": "Launchpad Ventures",
        "doc_dir": "test documents/Launchpad Ventures",
        "queries": [
            "Who is the Managing Partner?",
            "What is the Managing Partner's compensation?",
            "Who are the General Partners?",
            "Who reports to Alexandra Kim?",
            "What portfolio companies are in Cohort 12?",
            "Tell me about CloudAI",
            "Tell me about NeuralBox",
            "What is David Park's compensation?",
            "Who leads the Healthcare investments?",
            "What is the accelerator program structure?",
        ],
    },
]
