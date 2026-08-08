-- Run once in the Supabase SQL Editor after the app has created its tables.
-- The Streamlit backend connects directly to PostgreSQL. The Data API roles
-- must not be able to read family legal data.

alter table if exists public.cases enable row level security;
alter table if exists public.case_records enable row level security;
alter table if exists public.case_files enable row level security;
alter table if exists public.case_events enable row level security;
alter table if exists public.case_memories enable row level security;
alter table if exists public.analysis_cache enable row level security;
alter table if exists public.usage_events enable row level security;
alter table if exists public.user_profiles enable row level security;

revoke all on table public.cases from anon, authenticated;
revoke all on table public.case_records from anon, authenticated;
revoke all on table public.case_files from anon, authenticated;
revoke all on table public.case_events from anon, authenticated;
revoke all on table public.case_memories from anon, authenticated;
revoke all on table public.analysis_cache from anon, authenticated;
revoke all on table public.usage_events from anon, authenticated;
revoke all on table public.user_profiles from anon, authenticated;
