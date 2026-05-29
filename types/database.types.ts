export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      au_group_company_name_rules: {
        Row: {
          created_at: string
          enabled: boolean
          id: string
          notes: string | null
          pattern: string
          priority: number
          replacement: string
          rule_type: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          enabled?: boolean
          id?: string
          notes?: string | null
          pattern: string
          priority?: number
          replacement?: string
          rule_type: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          enabled?: boolean
          id?: string
          notes?: string | null
          pattern?: string
          priority?: number
          replacement?: string
          rule_type?: string
          updated_at?: string
        }
        Relationships: []
      }
      au_group_company_tiers: {
        Row: {
          active: boolean
          label: string
          min_employees: number | null
          min_revenue: number | null
          notes: string | null
          tier: number
          updated_at: string
        }
        Insert: {
          active?: boolean
          label: string
          min_employees?: number | null
          min_revenue?: number | null
          notes?: string | null
          tier: number
          updated_at?: string
        }
        Update: {
          active?: boolean
          label?: string
          min_employees?: number | null
          min_revenue?: number | null
          notes?: string | null
          tier?: number
          updated_at?: string
        }
        Relationships: []
      }
      au_group_config_audit: {
        Row: {
          action: string
          changed_at: string
          config_table: string
          id: number
          new_data: Json | null
          old_data: Json | null
          row_key: string | null
        }
        Insert: {
          action: string
          changed_at?: string
          config_table: string
          id?: number
          new_data?: Json | null
          old_data?: Json | null
          row_key?: string | null
        }
        Update: {
          action?: string
          changed_at?: string
          config_table?: string
          id?: number
          new_data?: Json | null
          old_data?: Json | null
          row_key?: string | null
        }
        Relationships: []
      }
      au_group_court_mappings: {
        Row: {
          active: boolean
          court_district: string
          court_id: string
          created_at: string
          state: string
          updated_at: string
        }
        Insert: {
          active?: boolean
          court_district: string
          court_id: string
          created_at?: string
          state: string
          updated_at?: string
        }
        Update: {
          active?: boolean
          court_district?: string
          court_id?: string
          created_at?: string
          state?: string
          updated_at?: string
        }
        Relationships: []
      }
      au_group_enrich_loop_staging: {
        Row: {
          created_at: string
          creditor_id: string
          job_id: string
          result: Json
          updated_at: string
        }
        Insert: {
          created_at?: string
          creditor_id: string
          job_id: string
          result?: Json
          updated_at?: string
        }
        Update: {
          created_at?: string
          creditor_id?: string
          job_id?: string
          result?: Json
          updated_at?: string
        }
        Relationships: []
      }
      au_group_runtime_config: {
        Row: {
          config_key: string
          config_value: string
          notes: string | null
          updated_at: string
        }
        Insert: {
          config_key: string
          config_value: string
          notes?: string | null
          updated_at?: string
        }
        Update: {
          config_key?: string
          config_value?: string
          notes?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      au_group_schedule_f_keywords: {
        Row: {
          active: boolean
          created_at: string
          id: number
          notes: string | null
          pattern: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          id?: number
          notes?: string | null
          pattern: string
        }
        Update: {
          active?: boolean
          created_at?: string
          id?: number
          notes?: string | null
          pattern?: string
        }
        Relationships: []
      }
      au_group_suppression_keywords: {
        Row: {
          active: boolean
          created_at: string
          id: number
          notes: string | null
          pattern: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          id?: number
          notes?: string | null
          pattern: string
        }
        Update: {
          active?: boolean
          created_at?: string
          id?: number
          notes?: string | null
          pattern?: string
        }
        Relationships: []
      }
      au_group_suppression_lenders: {
        Row: {
          active: boolean
          created_at: string
          id: number
          notes: string | null
          pattern: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          id?: number
          notes?: string | null
          pattern: string
        }
        Update: {
          active?: boolean
          created_at?: string
          id?: number
          notes?: string | null
          pattern?: string
        }
        Relationships: []
      }
      au_group_target_states: {
        Row: {
          active: boolean
          created_at: string
          notes: string | null
          state: string
          updated_at: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          notes?: string | null
          state: string
          updated_at?: string
        }
        Update: {
          active?: boolean
          created_at?: string
          notes?: string | null
          state?: string
          updated_at?: string
        }
        Relationships: []
      }
      au_group_territory_assignments: {
        Row: {
          created_at: string
          rep_name: string
          salesforce_user_id: string
          state: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          rep_name: string
          salesforce_user_id: string
          state: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          rep_name?: string
          salesforce_user_id?: string
          state?: string
          updated_at?: string
        }
        Relationships: []
      }
      au_group_tier_contact_titles: {
        Row: {
          active: boolean
          created_at: string
          id: number
          sort_order: number
          tier: number
          title_pattern: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          id?: number
          sort_order?: number
          tier: number
          title_pattern: string
        }
        Update: {
          active?: boolean
          created_at?: string
          id?: number
          sort_order?: number
          tier?: number
          title_pattern?: string
        }
        Relationships: [
          {
            foreignKeyName: "au_group_tier_contact_titles_tier_fkey"
            columns: ["tier"]
            isOneToOne: false
            referencedRelation: "au_group_company_tiers"
            referencedColumns: ["tier"]
          },
        ]
      }
      au_group_zoominfo_company_cache: {
        Row: {
          cache_key: string
          company_id: string
          created_at: string
          expires_at: string
          firmographics: Json
          match_confidence: number | null
          normalized_name: string | null
          raw_response: Json | null
          updated_at: string
        }
        Insert: {
          cache_key: string
          company_id: string
          created_at?: string
          expires_at: string
          firmographics?: Json
          match_confidence?: number | null
          normalized_name?: string | null
          raw_response?: Json | null
          updated_at?: string
        }
        Update: {
          cache_key?: string
          company_id?: string
          created_at?: string
          expires_at?: string
          firmographics?: Json
          match_confidence?: number | null
          normalized_name?: string | null
          raw_response?: Json | null
          updated_at?: string
        }
        Relationships: []
      }
      bankruptcies: {
        Row: {
          case_number: string
          chapter_type: Database["public"]["Enums"]["bankruptcy_chapter"]
          city: string | null
          court_district: string
          court_id: string | null
          created_at: string
          debtor_name: string
          estimated_assets: number | null
          estimated_assets_range: Json | null
          estimated_creditor_count: number | null
          estimated_creditor_count_range: Json | null
          estimated_liabilities: number | null
          estimated_liabilities_range: Json | null
          extraction_confidence_score: number | null
          filing_date: string
          forms_downloaded_at: string | null
          id: string
          industry_code: string | null
          is_business: boolean | null
          last_docket_check_at: string | null
          lead_priority: string | null
          lead_score: number | null
          manual_review_required: boolean
          monitoring_enabled: boolean | null
          rss_guid: string | null
          sales_ready: boolean | null
          source_type: string | null
          state: string
          updated_at: string
        }
        Insert: {
          case_number: string
          chapter_type: Database["public"]["Enums"]["bankruptcy_chapter"]
          city?: string | null
          court_district: string
          court_id?: string | null
          created_at?: string
          debtor_name: string
          estimated_assets?: number | null
          estimated_assets_range?: Json | null
          estimated_creditor_count?: number | null
          estimated_creditor_count_range?: Json | null
          estimated_liabilities?: number | null
          estimated_liabilities_range?: Json | null
          extraction_confidence_score?: number | null
          filing_date: string
          forms_downloaded_at?: string | null
          id?: string
          industry_code?: string | null
          is_business?: boolean | null
          last_docket_check_at?: string | null
          lead_priority?: string | null
          lead_score?: number | null
          manual_review_required?: boolean
          monitoring_enabled?: boolean | null
          rss_guid?: string | null
          sales_ready?: boolean | null
          source_type?: string | null
          state: string
          updated_at?: string
        }
        Update: {
          case_number?: string
          chapter_type?: Database["public"]["Enums"]["bankruptcy_chapter"]
          city?: string | null
          court_district?: string
          court_id?: string | null
          created_at?: string
          debtor_name?: string
          estimated_assets?: number | null
          estimated_assets_range?: Json | null
          estimated_creditor_count?: number | null
          estimated_creditor_count_range?: Json | null
          estimated_liabilities?: number | null
          estimated_liabilities_range?: Json | null
          extraction_confidence_score?: number | null
          filing_date?: string
          forms_downloaded_at?: string | null
          id?: string
          industry_code?: string | null
          is_business?: boolean | null
          last_docket_check_at?: string | null
          lead_priority?: string | null
          lead_score?: number | null
          manual_review_required?: boolean
          monitoring_enabled?: boolean | null
          rss_guid?: string | null
          sales_ready?: boolean | null
          source_type?: string | null
          state?: string
          updated_at?: string
        }
        Relationships: []
      }
      bankruptcy_case_status: {
        Row: {
          bankruptcy_id: string
          created_at: string | null
          docket_last_checked_at: string | null
          enrichment_completed: boolean | null
          has_asset_schedule: boolean | null
          has_creditor_matrix: boolean | null
          has_schedule_f: boolean | null
          latest_docket_number: number | null
          lifecycle_stage: string
          outreach_ready: boolean | null
          priority_score: number | null
          updated_at: string | null
        }
        Insert: {
          bankruptcy_id: string
          created_at?: string | null
          docket_last_checked_at?: string | null
          enrichment_completed?: boolean | null
          has_asset_schedule?: boolean | null
          has_creditor_matrix?: boolean | null
          has_schedule_f?: boolean | null
          latest_docket_number?: number | null
          lifecycle_stage?: string
          outreach_ready?: boolean | null
          priority_score?: number | null
          updated_at?: string | null
        }
        Update: {
          bankruptcy_id?: string
          created_at?: string | null
          docket_last_checked_at?: string | null
          enrichment_completed?: boolean | null
          has_asset_schedule?: boolean | null
          has_creditor_matrix?: boolean | null
          has_schedule_f?: boolean | null
          latest_docket_number?: number | null
          lifecycle_stage?: string
          outreach_ready?: boolean | null
          priority_score?: number | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "bankruptcy_case_status_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: true
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "bankruptcy_case_status_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: true
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
        ]
      }
      bankruptcy_creditors: {
        Row: {
          bankruptcy_id: string
          creditor_id: string
        }
        Insert: {
          bankruptcy_id: string
          creditor_id: string
        }
        Update: {
          bankruptcy_id?: string
          creditor_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "bankruptcy_creditors_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "bankruptcy_creditors_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "bankruptcy_creditors_creditor_id_fkey"
            columns: ["creditor_id"]
            isOneToOne: false
            referencedRelation: "creditors"
            referencedColumns: ["id"]
          },
        ]
      }
      bankruptcy_rss_events: {
        Row: {
          bankruptcy_id: string | null
          case_number: string
          court_id: string
          created_at: string
          event_number: string | null
          event_type: string | null
          id: string
          processed: boolean | null
          qualified: boolean | null
          raw_payload: Json | null
          rss_guid: string | null
          unique_key: string
        }
        Insert: {
          bankruptcy_id?: string | null
          case_number: string
          court_id: string
          created_at?: string
          event_number?: string | null
          event_type?: string | null
          id?: string
          processed?: boolean | null
          qualified?: boolean | null
          raw_payload?: Json | null
          rss_guid?: string | null
          unique_key: string
        }
        Update: {
          bankruptcy_id?: string | null
          case_number?: string
          court_id?: string
          created_at?: string
          event_number?: string | null
          event_type?: string | null
          id?: string
          processed?: boolean | null
          qualified?: boolean | null
          raw_payload?: Json | null
          rss_guid?: string | null
          unique_key?: string
        }
        Relationships: [
          {
            foreignKeyName: "bankruptcy_rss_events_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "bankruptcy_rss_events_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
        ]
      }
      creditor_matrix_extractions: {
        Row: {
          bankruptcy_id: string | null
          confidence_score: number | null
          created_at: string
          creditor_count: number
          document_id: string | null
          id: string
          manual_review_required: boolean
          parser_version: string
        }
        Insert: {
          bankruptcy_id?: string | null
          confidence_score?: number | null
          created_at?: string
          creditor_count?: number
          document_id?: string | null
          id?: string
          manual_review_required?: boolean
          parser_version: string
        }
        Update: {
          bankruptcy_id?: string | null
          confidence_score?: number | null
          created_at?: string
          creditor_count?: number
          document_id?: string | null
          id?: string
          manual_review_required?: boolean
          parser_version?: string
        }
        Relationships: [
          {
            foreignKeyName: "creditor_matrix_extractions_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creditor_matrix_extractions_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creditor_matrix_extractions_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
        ]
      }
      creditor_matrix_rows: {
        Row: {
          address: string | null
          claim_amount: number | null
          created_at: string
          creditor_name: string
          entity_type: string | null
          extraction_id: string
          id: string
          source_line_numbers: number[]
        }
        Insert: {
          address?: string | null
          claim_amount?: number | null
          created_at?: string
          creditor_name: string
          entity_type?: string | null
          extraction_id: string
          id?: string
          source_line_numbers?: number[]
        }
        Update: {
          address?: string | null
          claim_amount?: number | null
          created_at?: string
          creditor_name?: string
          entity_type?: string | null
          extraction_id?: string
          id?: string
          source_line_numbers?: number[]
        }
        Relationships: [
          {
            foreignKeyName: "creditor_matrix_rows_extraction_id_fkey"
            columns: ["extraction_id"]
            isOneToOne: false
            referencedRelation: "creditor_matrix_extractions"
            referencedColumns: ["id"]
          },
        ]
      }
      creditors: {
        Row: {
          address: string | null
          claim_amount: number | null
          claim_date: string | null
          confidence_score: number | null
          created_at: string
          dedup_audit: Json | null
          id: string
          is_company: boolean
          is_contingent: boolean
          is_disputed: boolean
          is_unliquidated: boolean
          name: string
          nature_of_claim: string | null
          normalized_name: string | null
          original_name: string | null
          source_bankruptcy_id: string | null
          updated_at: string
          zoominfo_company_id: string | null
          zoominfo_enriched_at: string | null
          zoominfo_firmographics: Json | null
          zoominfo_match_confidence: number | null
          zoominfo_match_status: string | null
        }
        Insert: {
          address?: string | null
          claim_amount?: number | null
          claim_date?: string | null
          confidence_score?: number | null
          created_at?: string
          dedup_audit?: Json | null
          id?: string
          is_company?: boolean
          is_contingent?: boolean
          is_disputed?: boolean
          is_unliquidated?: boolean
          name: string
          nature_of_claim?: string | null
          normalized_name?: string | null
          original_name?: string | null
          source_bankruptcy_id?: string | null
          updated_at?: string
          zoominfo_company_id?: string | null
          zoominfo_enriched_at?: string | null
          zoominfo_firmographics?: Json | null
          zoominfo_match_confidence?: number | null
          zoominfo_match_status?: string | null
        }
        Update: {
          address?: string | null
          claim_amount?: number | null
          claim_date?: string | null
          confidence_score?: number | null
          created_at?: string
          dedup_audit?: Json | null
          id?: string
          is_company?: boolean
          is_contingent?: boolean
          is_disputed?: boolean
          is_unliquidated?: boolean
          name?: string
          nature_of_claim?: string | null
          normalized_name?: string | null
          original_name?: string | null
          source_bankruptcy_id?: string | null
          updated_at?: string
          zoominfo_company_id?: string | null
          zoominfo_enriched_at?: string | null
          zoominfo_firmographics?: Json | null
          zoominfo_match_confidence?: number | null
          zoominfo_match_status?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "creditors_source_bankruptcy_id_fkey"
            columns: ["source_bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creditors_source_bankruptcy_id_fkey"
            columns: ["source_bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
        ]
      }
      docket_entries: {
        Row: {
          bankruptcy_id: string
          created_at: string | null
          description: string | null
          docket_number: string | null
          document_url: string | null
          filed_at: string | null
          id: string
          raw_payload: Json | null
          source_type: string | null
          title: string | null
        }
        Insert: {
          bankruptcy_id: string
          created_at?: string | null
          description?: string | null
          docket_number?: string | null
          document_url?: string | null
          filed_at?: string | null
          id?: string
          raw_payload?: Json | null
          source_type?: string | null
          title?: string | null
        }
        Update: {
          bankruptcy_id?: string
          created_at?: string | null
          description?: string | null
          docket_number?: string | null
          document_url?: string | null
          filed_at?: string | null
          id?: string
          raw_payload?: Json | null
          source_type?: string | null
          title?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "docket_entries_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "docket_entries_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
        ]
      }
      document_parse_results: {
        Row: {
          bankruptcy_id: string
          created_at: string
          doc_index: number
          doc_key: string
          document_id: string | null
          document_url: string | null
          id: string
          manual_review_required: boolean
          parse_error: string | null
          parser_result: Json | null
          parser_status: string
          processing_job_id: string
          s3_key: string | null
          updated_at: string
        }
        Insert: {
          bankruptcy_id: string
          created_at?: string
          doc_index: number
          doc_key: string
          document_id?: string | null
          document_url?: string | null
          id?: string
          manual_review_required?: boolean
          parse_error?: string | null
          parser_result?: Json | null
          parser_status: string
          processing_job_id: string
          s3_key?: string | null
          updated_at?: string
        }
        Update: {
          bankruptcy_id?: string
          created_at?: string
          doc_index?: number
          doc_key?: string
          document_id?: string | null
          document_url?: string | null
          id?: string
          manual_review_required?: boolean
          parse_error?: string | null
          parser_result?: Json | null
          parser_status?: string
          processing_job_id?: string
          s3_key?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "document_parse_results_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "document_parse_results_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "document_parse_results_processing_job_id_fkey"
            columns: ["processing_job_id"]
            isOneToOne: false
            referencedRelation: "processing_jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      documents: {
        Row: {
          bankruptcy_id: string | null
          content_sha256: string
          created_at: string
          filing_type: Database["public"]["Enums"]["au_group_filing_type"]
          id: string
          ocr_used: boolean
          page_count: number
          parse_mode: Database["public"]["Enums"]["au_group_parse_mode"]
          parser_version: string
          raw_extraction: Json | null
          s3_key: string
          updated_at: string
        }
        Insert: {
          bankruptcy_id?: string | null
          content_sha256: string
          created_at?: string
          filing_type?: Database["public"]["Enums"]["au_group_filing_type"]
          id?: string
          ocr_used?: boolean
          page_count?: number
          parse_mode?: Database["public"]["Enums"]["au_group_parse_mode"]
          parser_version: string
          raw_extraction?: Json | null
          s3_key: string
          updated_at?: string
        }
        Update: {
          bankruptcy_id?: string | null
          content_sha256?: string
          created_at?: string
          filing_type?: Database["public"]["Enums"]["au_group_filing_type"]
          id?: string
          ocr_used?: boolean
          page_count?: number
          parse_mode?: Database["public"]["Enums"]["au_group_parse_mode"]
          parser_version?: string
          raw_extraction?: Json | null
          s3_key?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "documents_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "documents_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
        ]
      }
      form201_extractions: {
        Row: {
          bankruptcy_id: string | null
          city: string | null
          confidence_score: number | null
          court_district: string | null
          created_at: string
          debtor_name: string | null
          document_id: string | null
          estimated_assets: Json | null
          estimated_creditor_count: Json | null
          estimated_liabilities: Json | null
          id: string
          industry_code: string | null
          manual_review_required: boolean
          parser_version: string
          raw_extraction: Json | null
          state: string | null
        }
        Insert: {
          bankruptcy_id?: string | null
          city?: string | null
          confidence_score?: number | null
          court_district?: string | null
          created_at?: string
          debtor_name?: string | null
          document_id?: string | null
          estimated_assets?: Json | null
          estimated_creditor_count?: Json | null
          estimated_liabilities?: Json | null
          id?: string
          industry_code?: string | null
          manual_review_required?: boolean
          parser_version: string
          raw_extraction?: Json | null
          state?: string | null
        }
        Update: {
          bankruptcy_id?: string | null
          city?: string | null
          confidence_score?: number | null
          court_district?: string | null
          created_at?: string
          debtor_name?: string | null
          document_id?: string | null
          estimated_assets?: Json | null
          estimated_creditor_count?: Json | null
          estimated_liabilities?: Json | null
          id?: string
          industry_code?: string | null
          manual_review_required?: boolean
          parser_version?: string
          raw_extraction?: Json | null
          state?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "form201_extractions_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "form201_extractions_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "form201_extractions_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
        ]
      }
      manual_review_queue: {
        Row: {
          assigned_to: string | null
          bankruptcy_id: string | null
          created_at: string
          document_id: string | null
          id: string
          review_reason: string
          status: Database["public"]["Enums"]["au_group_review_status"]
          updated_at: string
        }
        Insert: {
          assigned_to?: string | null
          bankruptcy_id?: string | null
          created_at?: string
          document_id?: string | null
          id?: string
          review_reason: string
          status?: Database["public"]["Enums"]["au_group_review_status"]
          updated_at?: string
        }
        Update: {
          assigned_to?: string | null
          bankruptcy_id?: string | null
          created_at?: string
          document_id?: string | null
          id?: string
          review_reason?: string
          status?: Database["public"]["Enums"]["au_group_review_status"]
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "manual_review_queue_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "manual_review_queue_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "manual_review_queue_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
        ]
      }
      pipeline_executions: {
        Row: {
          bankruptcy_id: string | null
          completed_at: string | null
          created_at: string
          duration_ms: number | null
          error_message: string | null
          id: number
          n8n_execution_id: string | null
          n8n_workflow_id: string | null
          node_name: string | null
          payload: Json | null
          processing_job_id: string | null
          status: string
        }
        Insert: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          duration_ms?: number | null
          error_message?: string | null
          id?: number
          n8n_execution_id?: string | null
          n8n_workflow_id?: string | null
          node_name?: string | null
          payload?: Json | null
          processing_job_id?: string | null
          status?: string
        }
        Update: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          duration_ms?: number | null
          error_message?: string | null
          id?: number
          n8n_execution_id?: string | null
          n8n_workflow_id?: string | null
          node_name?: string | null
          payload?: Json | null
          processing_job_id?: string | null
          status?: string
        }
        Relationships: [
          {
            foreignKeyName: "pipeline_executions_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "pipeline_executions_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "pipeline_executions_processing_job_id_fkey"
            columns: ["processing_job_id"]
            isOneToOne: false
            referencedRelation: "processing_jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      processing_jobs: {
        Row: {
          bankruptcy_id: string | null
          completed_at: string | null
          created_at: string
          error_message: string | null
          id: string
          job_payload: Json | null
          job_type: Database["public"]["Enums"]["au_group_job_type"]
          retry_count: number
          started_at: string | null
          status: Database["public"]["Enums"]["processing_job_status"]
          worker_name: string | null
        }
        Insert: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          error_message?: string | null
          id?: string
          job_payload?: Json | null
          job_type: Database["public"]["Enums"]["au_group_job_type"]
          retry_count?: number
          started_at?: string | null
          status: Database["public"]["Enums"]["processing_job_status"]
          worker_name?: string | null
        }
        Update: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          error_message?: string | null
          id?: string
          job_payload?: Json | null
          job_type?: Database["public"]["Enums"]["au_group_job_type"]
          retry_count?: number
          started_at?: string | null
          status?: Database["public"]["Enums"]["processing_job_status"]
          worker_name?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "processing_jobs_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "processing_jobs_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
        ]
      }
      salesforce_accounts: {
        Row: {
          created_at: string
          creditor_id: string
          id: string
          last_sync_at: string
          salesforce_account_id: string
          territory_rep: string | null
        }
        Insert: {
          created_at?: string
          creditor_id: string
          id?: string
          last_sync_at?: string
          salesforce_account_id: string
          territory_rep?: string | null
        }
        Update: {
          created_at?: string
          creditor_id?: string
          id?: string
          last_sync_at?: string
          salesforce_account_id?: string
          territory_rep?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "salesforce_accounts_creditor_id_fkey"
            columns: ["creditor_id"]
            isOneToOne: false
            referencedRelation: "creditors"
            referencedColumns: ["id"]
          },
        ]
      }
      schedule_f_queue: {
        Row: {
          ai_processed: boolean | null
          ai_summary: Json | null
          approved_at: string | null
          bankruptcy_id: string
          created_at: string
          detected_at: string | null
          docket_entry_number: string | null
          estimated_cost: number | null
          id: string
          last_error: string | null
          last_scanned_at: string | null
          monitoring_status: string | null
          next_scan_at: string | null
          pacer_document_url: string | null
          pacer_favorite_added_at: string | null
          page_count: number | null
          priority: number | null
          rejected_at: string | null
          scan_attempts: number | null
          schedule_f_detected: boolean | null
          status: string
        }
        Insert: {
          ai_processed?: boolean | null
          ai_summary?: Json | null
          approved_at?: string | null
          bankruptcy_id: string
          created_at?: string
          detected_at?: string | null
          docket_entry_number?: string | null
          estimated_cost?: number | null
          id?: string
          last_error?: string | null
          last_scanned_at?: string | null
          monitoring_status?: string | null
          next_scan_at?: string | null
          pacer_document_url?: string | null
          pacer_favorite_added_at?: string | null
          page_count?: number | null
          priority?: number | null
          rejected_at?: string | null
          scan_attempts?: number | null
          schedule_f_detected?: boolean | null
          status: string
        }
        Update: {
          ai_processed?: boolean | null
          ai_summary?: Json | null
          approved_at?: string | null
          bankruptcy_id?: string
          created_at?: string
          detected_at?: string | null
          docket_entry_number?: string | null
          estimated_cost?: number | null
          id?: string
          last_error?: string | null
          last_scanned_at?: string | null
          monitoring_status?: string | null
          next_scan_at?: string | null
          pacer_document_url?: string | null
          pacer_favorite_added_at?: string | null
          page_count?: number | null
          priority?: number | null
          rejected_at?: string | null
          scan_attempts?: number | null
          schedule_f_detected?: boolean | null
          status?: string
        }
        Relationships: [
          {
            foreignKeyName: "schedule_f_queue_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "active_monitored_cases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "schedule_f_queue_bankruptcy_id_fkey"
            columns: ["bankruptcy_id"]
            isOneToOne: false
            referencedRelation: "bankruptcies"
            referencedColumns: ["id"]
          },
        ]
      }
      zoom_info_contacts: {
        Row: {
          company_employee_count: number | null
          company_industry: string | null
          company_revenue: number | null
          created_at: string
          creditor_id: string
          email: string | null
          engagement_score: number | null
          full_name: string
          id: string
          phone: string | null
          title: string | null
        }
        Insert: {
          company_employee_count?: number | null
          company_industry?: string | null
          company_revenue?: number | null
          created_at?: string
          creditor_id: string
          email?: string | null
          engagement_score?: number | null
          full_name: string
          id?: string
          phone?: string | null
          title?: string | null
        }
        Update: {
          company_employee_count?: number | null
          company_industry?: string | null
          company_revenue?: number | null
          created_at?: string
          creditor_id?: string
          email?: string | null
          engagement_score?: number | null
          full_name?: string
          id?: string
          phone?: string | null
          title?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "zoom_info_contacts_creditor_id_fkey"
            columns: ["creditor_id"]
            isOneToOne: false
            referencedRelation: "creditors"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      active_monitored_cases: {
        Row: {
          case_number: string | null
          chapter_type: Database["public"]["Enums"]["bankruptcy_chapter"] | null
          court_id: string | null
          debtor_name: string | null
          filing_date: string | null
          id: string | null
          lead_priority: string | null
          lead_score: number | null
          monitoring_enabled: boolean | null
        }
        Insert: {
          case_number?: string | null
          chapter_type?:
            | Database["public"]["Enums"]["bankruptcy_chapter"]
            | null
          court_id?: string | null
          debtor_name?: string | null
          filing_date?: string | null
          id?: string | null
          lead_priority?: string | null
          lead_score?: number | null
          monitoring_enabled?: boolean | null
        }
        Update: {
          case_number?: string | null
          chapter_type?:
            | Database["public"]["Enums"]["bankruptcy_chapter"]
            | null
          court_id?: string | null
          debtor_name?: string | null
          filing_date?: string | null
          id?: string | null
          lead_priority?: string | null
          lead_score?: number | null
          monitoring_enabled?: boolean | null
        }
        Relationships: []
      }
    }
    Functions: {
      au_group_acquire_processing_job: {
        Args: {
          p_bankruptcy_id: string
          p_job_type: Database["public"]["Enums"]["au_group_job_type"]
          p_stale_interval?: string
        }
        Returns: Json
      }
      au_group_build_lookup_context: {
        Args: { p_ctx: Json; p_row: Json }
        Returns: Json
      }
      au_group_check_repeat_exposure: {
        Args: {
          p_creditor_id: string
          p_threshold?: number
          p_window_months?: number
        }
        Returns: {
          filing_count: number
          is_repeat: boolean
          suggested_message: string
          total_claim_amount: number
        }[]
      }
      au_group_classify_company_tier: {
        Args: { p_employees?: number; p_revenue?: number }
        Returns: number
      }
      au_group_company_lookup_cache_key: {
        Args: { p_address?: string; p_name: string }
        Returns: string
      }
      au_group_company_lookup_prepare: {
        Args: { p_address?: string; p_name: string }
        Returns: Json
      }
      au_group_config_bool: {
        Args: { p_default: boolean; p_key: string }
        Returns: boolean
      }
      au_group_config_int: {
        Args: { p_default: number; p_key: string }
        Returns: number
      }
      au_group_config_text: {
        Args: { p_default: string; p_key: string }
        Returns: string
      }
      au_group_count_company_creditors: {
        Args: { p_bankruptcy_id: string }
        Returns: number
      }
      au_group_creditor_pipeline_status: {
        Args: { p_creditor_id: string }
        Returns: string
      }
      au_group_daily_creditor_report_rows: {
        Args: { p_since?: string }
        Returns: Json
      }
      au_group_daily_pipeline_summary: {
        Args: { p_since?: string }
        Returns: Json
      }
      au_group_diff_pacer_favorites: {
        Args: { p_bankruptcy_ids?: string[]; p_favorites: Json }
        Returns: Json
      }
      au_group_enrich_loop_finalize: {
        Args: {
          p_bankruptcy_id?: string
          p_job_id: string
          p_pipeline_execution_id?: string
        }
        Returns: Json
      }
      au_group_enrich_loop_push: {
        Args: { p_creditor_id: string; p_job_id: string; p_result: Json }
        Returns: Json
      }
      au_group_evaluate_outreach_gates: {
        Args: {
          p_active_engagement?: boolean
          p_creditor_id: string
          p_dnc?: boolean
          p_repeat_threshold?: number
          p_repeat_window_months?: number
          p_suppress?: boolean
        }
        Returns: Json
      }
      au_group_expand_import_rows: { Args: { p_body: Json }; Returns: Json }
      au_group_fail_stale_processing_jobs: {
        Args: { p_max_age?: string }
        Returns: number
      }
      au_group_finalize_document_job: {
        Args: {
          p_job_id: string
          p_pipeline_execution_id?: string
          p_schedule_f_queue_id?: string
        }
        Returns: Json
      }
      au_group_get_runtime_config: { Args: { p_key: string }; Returns: string }
      au_group_get_zoominfo_company_cache: {
        Args: { p_cache_key: string }
        Returns: {
          cache_hit: boolean
          cache_key: string
          company_id: string
          firmographics: Json
          match_confidence: number
          normalized_name: string
        }[]
      }
      au_group_is_junk_creditor_name: {
        Args: { p_name: string }
        Returns: boolean
      }
      au_group_is_suppressed_creditor_name: {
        Args: { p_name: string }
        Returns: boolean
      }
      au_group_is_target_state: { Args: { p_state: string }; Returns: boolean }
      au_group_jsonb_midpoint_count: { Args: { range: Json }; Returns: number }
      au_group_jsonb_midpoint_usd: { Args: { range: Json }; Returns: number }
      au_group_link_document_bankruptcy: {
        Args: { p_bankruptcy_id: string; p_document_id: string }
        Returns: Json
      }
      au_group_list_company_creditors: {
        Args: { p_bankruptcy_id: string }
        Returns: {
          claim_amount: number
          creditor_address: string
          creditor_id: string
          creditor_name: string
          creditor_state: string
          normalized_name: string
        }[]
      }
      au_group_list_contact_titles: {
        Args: { p_include_fallback?: boolean; p_tier: number }
        Returns: string[]
      }
      au_group_list_pacer_poll_candidates: {
        Args: never
        Returns: {
          case_number: string
          chapter_type: Database["public"]["Enums"]["bankruptcy_chapter"]
          city: string | null
          court_district: string
          court_id: string | null
          created_at: string
          debtor_name: string
          estimated_assets: number | null
          estimated_assets_range: Json | null
          estimated_creditor_count: number | null
          estimated_creditor_count_range: Json | null
          estimated_liabilities: number | null
          estimated_liabilities_range: Json | null
          extraction_confidence_score: number | null
          filing_date: string
          forms_downloaded_at: string | null
          id: string
          industry_code: string | null
          is_business: boolean | null
          last_docket_check_at: string | null
          lead_priority: string | null
          lead_score: number | null
          manual_review_required: boolean
          monitoring_enabled: boolean | null
          rss_guid: string | null
          sales_ready: boolean | null
          source_type: string | null
          state: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "bankruptcies"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      au_group_list_target_states: { Args: never; Returns: string[] }
      au_group_merge_creditor_matrix:
        | {
            Args: { p_bankruptcy_id: string; p_creditors: Json }
            Returns: number
          }
        | {
            Args: {
              p_bankruptcy_id: string
              p_confidence_score?: number
              p_creditors: Json
            }
            Returns: number
          }
      au_group_normalize_company_name: {
        Args: { p_name: string }
        Returns: string
      }
      au_group_normalize_rss_item: { Args: { p_item: Json }; Returns: Json }
      au_group_normalize_rss_items: { Args: { p_items: Json }; Returns: Json }
      au_group_normalize_zoominfo_company_response: {
        Args: { p_body: Json; p_ctx: Json; p_status_code?: number }
        Returns: Json
      }
      au_group_normalize_zoominfo_contact_response: {
        Args: { p_body: Json; p_ctx: Json; p_status_code?: number }
        Returns: Json
      }
      au_group_parse_creditor_city: {
        Args: { p_address: string }
        Returns: string
      }
      au_group_parse_creditor_state: {
        Args: { p_address: string; p_fallback_state: string }
        Returns: string
      }
      au_group_pick_document_parse_handoff: {
        Args: { p_bankruptcy_id: string }
        Returns: Json
      }
      au_group_resolve_court_and_target_state: {
        Args: { p_court_id: string }
        Returns: {
          bankruptcy_state: string
          court_district: string
          is_target_state: boolean
          skip_reason: string
        }[]
      }
      au_group_resolve_court_mapping: {
        Args: { p_court_id: string }
        Returns: {
          court_district: string
          court_id: string
          state: string
        }[]
      }
      au_group_resolve_manual_review: {
        Args: { p_resolved_by?: string; p_review_id: string }
        Returns: Json
      }
      au_group_resolve_territory_rep: {
        Args: { p_state: string }
        Returns: {
          rep_name: string
          salesforce_user_id: string
          state: string
        }[]
      }
      au_group_safe_numeric: { Args: { p_text: string }; Returns: number }
      au_group_schedule_f_keyword_hit: {
        Args: { p_text: string }
        Returns: boolean
      }
      au_group_set_creditor_zoominfo_company_id: {
        Args: {
          p_company_id: string
          p_creditor_id: string
          p_firmographics?: Json
          p_match_confidence?: number
          p_match_status?: string
          p_normalized_name?: string
        }
        Returns: boolean
      }
      au_group_upsert_bankruptcy: {
        Args: {
          p_case_number: string
          p_chapter_type: Database["public"]["Enums"]["au_group_chapter_type"]
          p_court_district: string
          p_debtor_name: string
          p_estimated_assets?: number
          p_estimated_creditor_count?: number
          p_estimated_liabilities?: number
          p_filing_date: string
          p_state: string
        }
        Returns: string
      }
      au_group_upsert_bankruptcy_from_form201: {
        Args: {
          p_bankruptcy_id: string
          p_city?: string
          p_confidence_score?: number
          p_court_district?: string
          p_debtor_name?: string
          p_estimated_assets?: Json
          p_estimated_creditor_count?: Json
          p_estimated_liabilities?: Json
          p_industry_code?: string
          p_manual_review_required?: boolean
          p_state?: string
        }
        Returns: string
      }
      au_group_upsert_case_status: {
        Args: {
          p_bankruptcy_id: string
          p_enrichment_completed?: boolean
          p_has_asset_schedule?: boolean
          p_has_creditor_matrix?: boolean
          p_has_schedule_f?: boolean
          p_lifecycle_stage?: string
          p_outreach_ready?: boolean
        }
        Returns: string
      }
      au_group_upsert_docket_entries: {
        Args: { p_bankruptcy_id: string; p_entries: Json }
        Returns: number
      }
      au_group_upsert_document_parse_result: {
        Args: {
          p_bankruptcy_id: string
          p_doc_index: number
          p_doc_key: string
          p_document_id?: string
          p_document_url?: string
          p_manual_review_required?: boolean
          p_parse_error?: string
          p_parser_result?: Json
          p_parser_status: string
          p_processing_job_id: string
          p_s3_key?: string
        }
        Returns: Json
      }
      au_group_upsert_salesforce_account: {
        Args: {
          p_creditor_id: string
          p_salesforce_account_id: string
          p_territory_rep?: string
        }
        Returns: undefined
      }
      au_group_upsert_zoom_info_contacts: {
        Args: {
          p_company_employee_count?: number
          p_company_industry?: string
          p_company_revenue?: number
          p_contacts: Json
          p_creditor_id: string
        }
        Returns: number
      }
      au_group_upsert_zoominfo_company_cache: {
        Args: {
          p_cache_key: string
          p_company_id: string
          p_firmographics?: Json
          p_match_confidence?: number
          p_normalized_name?: string
          p_raw_response?: Json
          p_ttl_days?: number
        }
        Returns: boolean
      }
      au_group_zoominfo_company_url: {
        Args: { p_company_id: string }
        Returns: string
      }
    }
    Enums: {
      au_group_chapter_type: "11" | "7" | "11-Subchapter-V"
      au_group_filing_type:
        | "FORM_201"
        | "CREDITOR_MATRIX"
        | "SCHEDULE"
        | "SOFA"
        | "UNKNOWN"
      au_group_job_status:
        | "pending"
        | "running"
        | "completed"
        | "failed"
        | "manual_review_required"
      au_group_job_type:
        | "pacer_poll"
        | "document_parse"
        | "zoom_info_enrich"
        | "salesforce_push"
        | "document_intelligence"
      au_group_parse_mode: "structured" | "ocr"
      au_group_review_status: "pending" | "in_review" | "resolved" | "rejected"
      au_group_schedule_f_status:
        | "monitoring"
        | "detected"
        | "pending_approval"
        | "approved"
        | "rejected"
        | "processed"
      bankruptcy_chapter: "7" | "11" | "13" | "15"
      processing_job_status:
        | "queued"
        | "running"
        | "completed"
        | "failed"
        | "retrying"
      schedule_f_status:
        | "pending"
        | "monitoring"
        | "detected"
        | "downloaded"
        | "parsed"
        | "failed"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      au_group_chapter_type: ["11", "7", "11-Subchapter-V"],
      au_group_filing_type: [
        "FORM_201",
        "CREDITOR_MATRIX",
        "SCHEDULE",
        "SOFA",
        "UNKNOWN",
      ],
      au_group_job_status: [
        "pending",
        "running",
        "completed",
        "failed",
        "manual_review_required",
      ],
      au_group_job_type: [
        "pacer_poll",
        "document_parse",
        "zoom_info_enrich",
        "salesforce_push",
        "document_intelligence",
      ],
      au_group_parse_mode: ["structured", "ocr"],
      au_group_review_status: ["pending", "in_review", "resolved", "rejected"],
      au_group_schedule_f_status: [
        "monitoring",
        "detected",
        "pending_approval",
        "approved",
        "rejected",
        "processed",
      ],
      bankruptcy_chapter: ["7", "11", "13", "15"],
      processing_job_status: [
        "queued",
        "running",
        "completed",
        "failed",
        "retrying",
      ],
      schedule_f_status: [
        "pending",
        "monitoring",
        "detected",
        "downloaded",
        "parsed",
        "failed",
      ],
    },
  },
} as const

