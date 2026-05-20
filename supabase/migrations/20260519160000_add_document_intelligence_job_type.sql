-- Add document_intelligence to processing_jobs job_type enum (SYS-02 orchestration)
alter type public.au_group_job_type add value if not exists 'document_intelligence';
