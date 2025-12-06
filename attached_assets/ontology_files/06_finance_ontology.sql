-- =============================================================================
-- Context Foundry: Financial Services & Capital Markets Domain Template
-- =============================================================================
-- Archetype: FINANCE (ID: 06)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Claude (Integration Pass)
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- Companies Served: Abu Dhabi Securities Exchange (ADX), Wio Bank, Odeabank
-- =============================================================================

-- =============================================================================
-- SHARED TYPE REFERENCES (from shared_ontology.sql - DO NOT REDEFINE)
-- =============================================================================
-- Facility: 20000000-0000-0001-0000-000000000001
-- Good: 20000000-0000-0002-0000-000000000001
-- OperationalTeam: 20000000-0000-0004-0000-000000000001
-- OperationalDocument: 20000000-0000-0005-0000-000000000001
-- RegulatoryFiling: 20000000-0000-0005-0000-000000000005

-- =============================================================================
-- ENTITY TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Abstract Types
('20000000-0006-0000-0000-000000000001', 'FinancialFacility', 2, 'Financial Facility',
 'Abstract parent for financial services facilities.',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"facility_type": {"type": "string"}, "regulatory_license": {"type": "string"}}}',
 '["financial facility", "bank", "exchange", "branch"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000002', 'FinancialEvent', 2, 'Financial Event',
 'Abstract parent for financial transactions and events.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"event_time": {"type": "string", "format": "date-time"}, "event_type": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "executed", "settled", "cancelled", "failed"]}}}',
 '["transaction", "trade", "event", "settlement"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000003', 'FinancialInstrument', 2, 'Financial Instrument',
 'Abstract parent for tradeable financial products.',
 '20000000-0000-0002-0000-000000000001',
 '{"type": "object", "properties": {"instrument_type": {"type": "string"}, "isin": {"type": "string"}, "currency": {"type": "string"}}}',
 '["instrument", "security", "product", "asset"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000004', 'FinancialAccount', 2, 'Financial Account',
 'Abstract parent for all account types.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"account_number": {"type": "string"}, "account_type": {"type": "string"}, "currency": {"type": "string"}, "status": {"type": "string", "enum": ["active", "dormant", "closed", "frozen"]}}}',
 '["account", "account number", "IBAN"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Facility Types
('20000000-0006-0000-0000-000000000005', 'BankBranch', 2, 'Bank Branch',
 'Physical bank branch location.',
 '20000000-0006-0000-0000-000000000001',
 '{"type": "object", "properties": {"branch_code": {"type": "string"}, "branch_name": {"type": "string"}, "services": {"type": "array", "items": {"type": "string"}}, "atm_count": {"type": "integer"}}}',
 '["branch", "bank branch", "Wio", "Odeabank", "branch code"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000006', 'TradingFloor', 2, 'Trading Floor',
 'Securities exchange trading venue.',
 '20000000-0006-0000-0000-000000000001',
 '{"type": "object", "properties": {"exchange_code": {"type": "string"}, "trading_hours": {"type": "string"}, "market_segments": {"type": "array", "items": {"type": "string"}}}}',
 '["trading floor", "exchange", "ADX", "Abu Dhabi Securities Exchange", "market"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000007', 'DataCenter', 2, 'Data Center',
 'Financial services data center for trading and banking systems.',
 '20000000-0006-0000-0000-000000000001',
 '{"type": "object", "properties": {"tier_level": {"type": "integer"}, "capacity_racks": {"type": "integer"}, "disaster_recovery": {"type": "boolean"}}}',
 '["data center", "primary site", "DR site", "colocation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Account Types
('20000000-0006-0000-0000-000000000008', 'BankAccount', 2, 'Bank Account',
 'Deposit or current bank account.',
 '20000000-0006-0000-0000-000000000004',
 '{"type": "object", "properties": {"iban": {"type": "string"}, "account_type": {"type": "string", "enum": ["current", "savings", "fixed_deposit", "business"]}, "balance": {"type": "number"}, "overdraft_limit": {"type": "number"}}}',
 '["bank account", "current account", "savings account", "IBAN", "deposit account"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000009', 'BrokerageAccount', 2, 'Brokerage Account',
 'Securities trading and investment account.',
 '20000000-0006-0000-0000-000000000004',
 '{"type": "object", "properties": {"investor_number": {"type": "string"}, "account_type": {"type": "string", "enum": ["retail", "institutional", "margin"]}, "portfolio_value": {"type": "number"}}}',
 '["brokerage account", "trading account", "investment account", "NIN", "investor number"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-00000000000A', 'CustodyAccount', 2, 'Custody Account',
 'Securities custody and safekeeping account.',
 '20000000-0006-0000-0000-000000000004',
 '{"type": "object", "properties": {"custodian": {"type": "string"}, "assets_under_custody": {"type": "number"}, "sub_custodians": {"type": "array", "items": {"type": "string"}}}}',
 '["custody account", "safekeeping", "custodian", "AUC"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Instrument Types
('20000000-0006-0000-0000-00000000000B', 'Equity', 2, 'Equity',
 'Listed equity security (stock/share).',
 '20000000-0006-0000-0000-000000000003',
 '{"type": "object", "properties": {"ticker": {"type": "string"}, "company_name": {"type": "string"}, "exchange": {"type": "string"}, "market_cap": {"type": "number"}, "sector": {"type": "string"}}}',
 '["equity", "stock", "share", "ticker", "listed company", "ADX listing"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-00000000000C', 'Bond', 2, 'Bond',
 'Fixed income debt security.',
 '20000000-0006-0000-0000-000000000003',
 '{"type": "object", "properties": {"coupon_rate": {"type": "number"}, "maturity_date": {"type": "string", "format": "date"}, "face_value": {"type": "number"}, "issuer": {"type": "string"}, "rating": {"type": "string"}}}',
 '["bond", "sukuk", "fixed income", "coupon", "maturity", "debt security"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-00000000000D', 'Fund', 2, 'Fund',
 'Investment fund (mutual fund, ETF).',
 '20000000-0006-0000-0000-000000000003',
 '{"type": "object", "properties": {"fund_type": {"type": "string", "enum": ["mutual_fund", "etf", "reit", "hedge_fund"]}, "nav": {"type": "number"}, "aum": {"type": "number"}, "expense_ratio": {"type": "number"}}}',
 '["fund", "ETF", "mutual fund", "REIT", "NAV", "investment fund"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-00000000000E', 'Loan', 2, 'Loan',
 'Credit facility or loan product.',
 '20000000-0006-0000-0000-000000000003',
 '{"type": "object", "properties": {"loan_type": {"type": "string", "enum": ["personal", "mortgage", "auto", "commercial", "credit_line"]}, "principal": {"type": "number"}, "interest_rate": {"type": "number"}, "term_months": {"type": "integer"}, "collateral": {"type": "string"}}}',
 '["loan", "credit", "mortgage", "financing", "facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Agent Types
('20000000-0006-0000-0000-00000000000F', 'AccountHolder', 2, 'Account Holder',
 'Individual or entity holding a financial account.',
 '10000000-0000-0000-0000-000000000004',
 '{"type": "object", "properties": {"customer_id": {"type": "string"}, "customer_type": {"type": "string", "enum": ["individual", "corporate", "institutional"]}, "kyc_status": {"type": "string"}, "risk_rating": {"type": "string"}}}',
 '["account holder", "customer", "client", "investor", "depositor"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000010', 'TradingDesk', 2, 'Trading Desk',
 'Team executing trades in specific asset classes.',
 '20000000-0000-0004-0000-000000000001',
 '{"type": "object", "properties": {"desk_type": {"type": "string", "enum": ["equities", "fixed_income", "fx", "derivatives", "commodities"]}, "traders": {"type": "integer"}, "trading_limits": {"type": "number"}}}',
 '["trading desk", "desk", "equities desk", "fixed income desk", "FX desk"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Event Types
('20000000-0006-0000-0000-000000000011', 'SecuritiesTrade', 2, 'SecuritiesTrade',
 'Securities trade execution.',
 '20000000-0006-0000-0000-000000000002',
 '{"type": "object", "properties": {"trade_id": {"type": "string"}, "trade_type": {"type": "string", "enum": ["buy", "sell", "short_sell"]}, "quantity": {"type": "number"}, "price": {"type": "number"}, "value": {"type": "number"}, "execution_time": {"type": "string", "format": "date-time"}}}',
 '["trade", "buy", "sell", "execution", "order filled", "traded"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000012', 'Settlement', 2, 'Settlement',
 'Trade settlement and clearing event.',
 '20000000-0006-0000-0000-000000000002',
 '{"type": "object", "properties": {"settlement_id": {"type": "string"}, "settlement_date": {"type": "string", "format": "date"}, "settlement_type": {"type": "string", "enum": ["T+0", "T+1", "T+2", "T+3"]}, "settlement_amount": {"type": "number"}}}',
 '["settlement", "cleared", "settled", "DVP", "delivery versus payment"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000013', 'BankingTransaction', 2, 'Banking Transaction',
 'Bank account transaction (deposit, withdrawal, transfer).',
 '20000000-0006-0000-0000-000000000002',
 '{"type": "object", "properties": {"transaction_id": {"type": "string"}, "transaction_type": {"type": "string", "enum": ["deposit", "withdrawal", "transfer", "payment", "fee"]}, "amount": {"type": "number"}, "reference": {"type": "string"}}}',
 '["transaction", "deposit", "withdrawal", "transfer", "payment"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000014', 'CorporateAction', 2, 'Corporate Action',
 'Corporate action affecting securities (dividend, split, rights).',
 '20000000-0006-0000-0000-000000000002',
 '{"type": "object", "properties": {"action_type": {"type": "string", "enum": ["dividend", "split", "rights", "merger", "bonus", "redemption"]}, "ex_date": {"type": "string", "format": "date"}, "record_date": {"type": "string", "format": "date"}, "payment_date": {"type": "string", "format": "date"}, "rate": {"type": "number"}}}',
 '["corporate action", "dividend", "stock split", "rights issue", "bonus shares"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Record Types
('20000000-0006-0000-0000-000000000015', 'AccountStatement', 2, 'Account Statement',
 'Periodic account statement.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"statement_date": {"type": "string", "format": "date"}, "period_start": {"type": "string", "format": "date"}, "period_end": {"type": "string", "format": "date"}, "opening_balance": {"type": "number"}, "closing_balance": {"type": "number"}}}',
 '["statement", "account statement", "bank statement", "portfolio statement"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000016', 'SecuritiesConfirmation', 2, 'Trade Confirmation',
 'Trade execution confirmation document.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"confirmation_number": {"type": "string"}, "trade_date": {"type": "string", "format": "date"}, "settlement_date": {"type": "string", "format": "date"}}}',
 '["confirmation", "trade confirmation", "contract note", "execution report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000017', 'RegulatoryReport', 2, 'Regulatory Report',
 'Report submitted to financial regulators.',
 '20000000-0000-0005-0000-000000000005',
 '{"type": "object", "properties": {"report_type": {"type": "string", "enum": ["AML", "capital_adequacy", "liquidity", "disclosure", "suspicious_activity"]}, "regulator": {"type": "string"}, "reporting_period": {"type": "string"}, "submission_deadline": {"type": "string", "format": "date"}}}',
 '["regulatory report", "SCA filing", "central bank report", "AML report", "capital report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Entity Types (from QA review)
('20000000-0006-0000-0000-000000000018', 'ComplianceCheck', 2, 'Compliance Check',
 'KYC, AML, or regulatory compliance verification event.',
 '20000000-0006-0000-0000-000000000002',
 '{"type": "object", "properties": {"check_id": {"type": "string"}, "check_type": {"type": "string", "enum": ["KYC", "AML", "sanctions", "PEP", "source_of_funds", "periodic_review"]}, "check_date": {"type": "string", "format": "date-time"}, "result": {"type": "string", "enum": ["pass", "fail", "review_required", "escalated"]}, "risk_rating": {"type": "string", "enum": ["low", "medium", "high", "prohibited"]}, "reviewer": {"type": "string"}, "next_review_date": {"type": "string", "format": "date"}}}',
 '["compliance check", "KYC", "AML check", "sanctions screening", "PEP check", "due diligence", "customer review"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-000000000019', 'PortfolioRebalancing', 2, 'Portfolio Rebalancing',
 'Portfolio rebalancing or reallocation event.',
 '20000000-0006-0000-0000-000000000002',
 '{"type": "object", "properties": {"rebalance_id": {"type": "string"}, "rebalance_date": {"type": "string", "format": "date-time"}, "trigger": {"type": "string", "enum": ["periodic", "threshold", "market_event", "client_request"]}, "trades_count": {"type": "integer"}, "turnover_percentage": {"type": "number"}, "before_allocation": {"type": "string"}, "after_allocation": {"type": "string"}}}',
 '["rebalancing", "portfolio rebalance", "reallocation", "portfolio adjustment", "tactical allocation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-00000000001A', 'CreditProduct', 2, 'Credit Product',
 'Abstract parent for credit and lending products.',
 '20000000-0006-0000-0000-000000000003',
 '{"type": "object", "properties": {"credit_type": {"type": "string"}, "interest_rate": {"type": "number"}, "rate_type": {"type": "string", "enum": ["fixed", "variable", "mixed"]}}}',
 '["credit product", "lending product", "credit facility", "financing"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-00000000001B', 'MarketData', 2, 'Market Data',
 'Market price, rate, or index data point.',
 '00000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"data_type": {"type": "string", "enum": ["price", "rate", "index", "fx_rate", "yield"]}, "symbol": {"type": "string"}, "value": {"type": "number"}, "timestamp": {"type": "string", "format": "date-time"}, "source": {"type": "string"}}}',
 '["market data", "price", "rate", "index", "FX rate", "yield", "quote", "ticker"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0006-0000-0000-00000000001C', 'RiskAssessment', 2, 'Risk Assessment',
 'Risk evaluation for customer, product, or transaction.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"assessment_id": {"type": "string"}, "assessment_type": {"type": "string", "enum": ["credit_risk", "market_risk", "operational_risk", "customer_risk"]}, "risk_score": {"type": "number"}, "risk_rating": {"type": "string", "enum": ["low", "medium", "high", "very_high"]}, "assessment_date": {"type": "string", "format": "date"}, "valid_until": {"type": "string", "format": "date"}}}',
 '["risk assessment", "risk rating", "credit score", "risk evaluation", "risk analysis"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- RELATIONSHIP TYPES
-- =============================================================================

INSERT INTO ontology.relations (
    id, relation_type, source_type_id, target_type_id, 
    cardinality, semantics, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('30000000-0006-0000-0000-000000000001', 'ACCOUNT_AT', 
 '20000000-0006-0000-0000-000000000004', '20000000-0006-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Account is held at a financial facility',
 '["account at", "held at", "with bank", "at branch"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000002', 'ACCOUNT_OWNED_BY', 
 '20000000-0006-0000-0000-000000000004', '20000000-0006-0000-0000-00000000000F',
 'MANY_TO_ONE',
 'Account is owned by an account holder',
 '["owned by", "holder", "customer", "account of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000003', 'TRADE_IN', 
 '20000000-0006-0000-0000-000000000011', '20000000-0006-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Trade is in a financial instrument',
 '["trade in", "traded", "bought", "sold", "security"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000004', 'TRADE_BY', 
 '20000000-0006-0000-0000-000000000011', '20000000-0006-0000-0000-000000000009',
 'MANY_TO_ONE',
 'Trade executed through brokerage account',
 '["traded by", "account", "through account", "investor"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000005', 'TRADE_ON', 
 '20000000-0006-0000-0000-000000000011', '20000000-0006-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Trade executed on trading floor/exchange',
 '["traded on", "on exchange", "ADX", "market"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000006', 'SETTLES_TRADE', 
 '20000000-0006-0000-0000-000000000012', '20000000-0006-0000-0000-000000000011',
 'ONE_TO_ONE',
 'Settlement settles a trade',
 '["settles", "settlement for", "clears"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000007', 'TRANSACTION_ON', 
 '20000000-0006-0000-0000-000000000013', '20000000-0006-0000-0000-000000000008',
 'MANY_TO_ONE',
 'Banking transaction on a bank account',
 '["on account", "from account", "to account", "credited", "debited"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000008', 'ACTION_AFFECTS', 
 '20000000-0006-0000-0000-000000000014', '20000000-0006-0000-0000-00000000000B',
 'MANY_TO_ONE',
 'Corporate action affects an equity',
 '["affects", "for security", "on stock", "dividend for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000009', 'LISTED_ON', 
 '20000000-0006-0000-0000-00000000000B', '20000000-0006-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Equity is listed on exchange',
 '["listed on", "traded on", "ADX listed", "exchange listing"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000000A', 'STATEMENT_FOR', 
 '20000000-0006-0000-0000-000000000015', '20000000-0006-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Statement is for an account',
 '["statement for", "account statement", "for account"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000000B', 'CONFIRMATION_FOR', 
 '20000000-0006-0000-0000-000000000016', '20000000-0006-0000-0000-000000000011',
 'ONE_TO_ONE',
 'Confirmation is for a trade',
 '["confirms", "confirmation for", "trade confirmed"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000000C', 'REPORT_BY', 
 '20000000-0006-0000-0000-000000000017', '20000000-0006-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Regulatory report submitted by financial facility',
 '["submitted by", "filed by", "reported by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000000D', 'LOAN_TO', 
 '20000000-0006-0000-0000-00000000000E', '20000000-0006-0000-0000-00000000000F',
 'MANY_TO_ONE',
 'Loan extended to account holder',
 '["loan to", "borrower", "credit to", "financing for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000000E', 'LOAN_FROM', 
 '20000000-0006-0000-0000-00000000000E', '20000000-0006-0000-0000-000000000005',
 'MANY_TO_ONE',
 'Loan originated from bank branch',
 '["loan from", "originated by", "lender", "financed by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000000F', 'CUSTODY_HOLDS', 
 '20000000-0006-0000-0000-00000000000A', '20000000-0006-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Custody account holds financial instruments',
 '["holds", "custody of", "safekeeping", "assets held"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000010', 'DESK_TRADES', 
 '20000000-0006-0000-0000-000000000010', '20000000-0006-0000-0000-000000000011',
 'ONE_TO_MANY',
 'Trading desk executes trades',
 '["executed by", "traded by desk", "desk trade"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000011', 'FUND_HOLDS', 
 '20000000-0006-0000-0000-00000000000D', '20000000-0006-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Fund holds financial instruments in portfolio',
 '["holds", "portfolio", "invested in", "fund holdings"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000012', 'DATA_CENTER_SUPPORTS', 
 '20000000-0006-0000-0000-000000000007', '20000000-0006-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Data center supports trading floor operations',
 '["supports", "hosts", "infrastructure for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000013', 'BOND_ISSUED_BY', 
 '20000000-0006-0000-0000-00000000000C', '10000000-0000-0000-0000-000000000005',
 'MANY_TO_ONE',
 'Bond is issued by an organization',
 '["issued by", "issuer", "borrower", "debt of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Relationships (from QA review)
('30000000-0006-0000-0000-000000000014', 'COMPLIANCE_FOR_CUSTOMER', 
 '20000000-0006-0000-0000-000000000018', '20000000-0006-0000-0000-00000000000F',
 'MANY_TO_ONE',
 'Compliance check is for a customer',
 '["compliance for", "KYC for customer", "due diligence on"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000015', 'COMPLIANCE_FOR_ACCOUNT', 
 '20000000-0006-0000-0000-000000000018', '20000000-0006-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Compliance check is for an account',
 '["account review", "KYC for account", "account compliance"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000016', 'REBALANCE_FOR_ACCOUNT', 
 '20000000-0006-0000-0000-000000000019', '20000000-0006-0000-0000-000000000009',
 'MANY_TO_ONE',
 'Portfolio rebalancing is for a brokerage account',
 '["rebalance for", "portfolio adjustment for", "reallocation for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000017', 'REBALANCE_TRIGGERS_TRADE', 
 '20000000-0006-0000-0000-000000000019', '20000000-0006-0000-0000-000000000011',
 'ONE_TO_MANY',
 'Portfolio rebalancing triggers trades',
 '["triggers trade", "rebalance trade", "resulting trade"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000018', 'LOAN_IS_CREDIT_PRODUCT', 
 '20000000-0006-0000-0000-00000000000E', '20000000-0006-0000-0000-00000000001A',
 'MANY_TO_ONE',
 'Loan is a type of credit product',
 '["credit product", "loan product", "financing product"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-000000000019', 'MARKET_DATA_FOR_INSTRUMENT', 
 '20000000-0006-0000-0000-00000000001B', '20000000-0006-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Market data is for a financial instrument',
 '["price of", "rate for", "quote for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000001A', 'RISK_FOR_CUSTOMER', 
 '20000000-0006-0000-0000-00000000001C', '20000000-0006-0000-0000-00000000000F',
 'MANY_TO_ONE',
 'Risk assessment is for a customer',
 '["risk for", "customer risk", "credit rating for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0006-0000-0000-00000000001B', 'RISK_FOR_LOAN', 
 '20000000-0006-0000-0000-00000000001C', '20000000-0006-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Risk assessment is for a loan',
 '["loan risk", "credit risk for", "risk assessment for loan"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- End of Financial Services Domain Template
-- =============================================================================
