// Generated from Supabase project umivttszdnsrosbqryia (AU Group pipeline only).
// Regenerate: Supabase MCP `generate_typescript_types` or `supabase gen types typescript --project-id umivttszdnsrosbqryia`

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      bankruptcies: {
        Row: {
          case_number: string
          chapter_type: Database["public"]["Enums"]["au_group_chapter_type"]
          court_district: string
          created_at: string
          debtor_name: string
          estimated_assets: number | null
          estimated_creditor_count: number | null
          estimated_liabilities: number | null
          filing_date: string
          forms_downloaded_at: string | null
          id: string
          state: string
          updated_at: string
        }
        Insert: {
          case_number: string
          chapter_type: Database["public"]["Enums"]["au_group_chapter_type"]
          court_district: string
          created_at?: string
          debtor_name: string
          estimated_assets?: number | null
          estimated_creditor_count?: number | null
          estimated_liabilities?: number | null
          filing_date: string
          forms_downloaded_at?: string | null
          id?: string
          state: string
          updated_at?: string
        }
        Update: {
          case_number?: string
          chapter_type?: Database["public"]["Enums"]["au_group_chapter_type"]
          court_district?: string
          created_at?: string
          debtor_name?: string
          estimated_assets?: number | null
          estimated_creditor_count?: number | null
          estimated_liabilities?: number | null
          filing_date?: string
          forms_downloaded_at?: string | null
          id?: string
          state?: string
          updated_at?: string
        }
        Relationships: []
      }
      bankruptcy_creditors: {
        Row: { bankruptcy_id: string; creditor_id: string }
        Insert: { bankruptcy_id: string; creditor_id: string }
        Update: { bankruptcy_id?: string; creditor_id?: string }
        Relationships: [
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
      creditors: {
        Row: {
          address: string | null
          claim_amount: number | null
          claim_date: string | null
          created_at: string
          id: string
          is_company: boolean
          is_contingent: boolean
          is_disputed: boolean
          is_unliquidated: boolean
          name: string
          nature_of_claim: string | null
          updated_at: string
        }
        Insert: {
          address?: string | null
          claim_amount?: number | null
          claim_date?: string | null
          created_at?: string
          id?: string
          is_company?: boolean
          is_contingent?: boolean
          is_disputed?: boolean
          is_unliquidated?: boolean
          name: string
          nature_of_claim?: string | null
          updated_at?: string
        }
        Update: {
          address?: string | null
          claim_amount?: number | null
          claim_date?: string | null
          created_at?: string
          id?: string
          is_company?: boolean
          is_contingent?: boolean
          is_disputed?: boolean
          is_unliquidated?: boolean
          name?: string
          nature_of_claim?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      pipeline_executions: {
        Row: {
          bankruptcy_id: string | null
          completed_at: string | null
          created_at: string
          error_message: string | null
          id: number
          n8n_execution_id: string | null
          n8n_workflow_id: string | null
          payload: Json | null
          processing_job_id: string | null
          status: string
        }
        Insert: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          error_message?: string | null
          id?: number
          n8n_execution_id?: string | null
          n8n_workflow_id?: string | null
          payload?: Json | null
          processing_job_id?: string | null
          status?: string
        }
        Update: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          error_message?: string | null
          id?: number
          n8n_execution_id?: string | null
          n8n_workflow_id?: string | null
          payload?: Json | null
          processing_job_id?: string | null
          status?: string
        }
        Relationships: [
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
          job_type: Database["public"]["Enums"]["au_group_job_type"]
          retry_count: number
          started_at: string | null
          status: Database["public"]["Enums"]["au_group_job_status"]
        }
        Insert: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          error_message?: string | null
          id?: string
          job_type: Database["public"]["Enums"]["au_group_job_type"]
          retry_count?: number
          started_at?: string | null
          status: Database["public"]["Enums"]["au_group_job_status"]
        }
        Update: {
          bankruptcy_id?: string | null
          completed_at?: string | null
          created_at?: string
          error_message?: string | null
          id?: string
          job_type?: Database["public"]["Enums"]["au_group_job_type"]
          retry_count?: number
          started_at?: string | null
          status?: Database["public"]["Enums"]["au_group_job_status"]
        }
        Relationships: [
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
          approved_at: string | null
          bankruptcy_id: string
          created_at: string
          detected_at: string | null
          docket_entry_number: string | null
          estimated_cost: number | null
          id: string
          last_scanned_at: string | null
          page_count: number | null
          status: Database["public"]["Enums"]["au_group_schedule_f_status"]
        }
        Insert: {
          approved_at?: string | null
          bankruptcy_id: string
          created_at?: string
          detected_at?: string | null
          docket_entry_number?: string | null
          estimated_cost?: number | null
          id?: string
          last_scanned_at?: string | null
          page_count?: number | null
          status: Database["public"]["Enums"]["au_group_schedule_f_status"]
        }
        Update: {
          approved_at?: string | null
          bankruptcy_id?: string
          created_at?: string
          detected_at?: string | null
          docket_entry_number?: string | null
          estimated_cost?: number | null
          id?: string
          last_scanned_at?: string | null
          page_count?: number | null
          status?: Database["public"]["Enums"]["au_group_schedule_f_status"]
        }
        Relationships: [
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
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      au_group_chapter_type: "11" | "7" | "11-Subchapter-V"
      au_group_job_status: "pending" | "running" | "completed" | "failed"
      au_group_job_type:
        | "pacer_poll"
        | "document_parse"
        | "zoom_info_enrich"
        | "salesforce_push"
      au_group_schedule_f_status:
        | "monitoring"
        | "detected"
        | "pending_approval"
        | "approved"
        | "rejected"
        | "processed"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  PublicTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends PublicTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
    ? keyof (DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = PublicTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? (DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : PublicTableNameOrOptions extends keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] & DefaultSchema["Views"])[PublicTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  PublicTableNameOrOptions extends keyof DefaultSchema["Tables"] | { schema: keyof DatabaseWithoutInternals },
  TableName extends PublicTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
    ? keyof DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = PublicTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : PublicTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][PublicTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  PublicTableNameOrOptions extends keyof DefaultSchema["Tables"] | { schema: keyof DatabaseWithoutInternals },
  TableName extends PublicTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
    ? keyof DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = PublicTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : PublicTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][PublicTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  PublicEnumNameOrOptions extends keyof DefaultSchema["Enums"] | { schema: keyof DatabaseWithoutInternals },
  EnumName extends PublicEnumNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
    ? keyof DatabaseWithoutInternals[PublicEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = PublicEnumNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : PublicEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][PublicEnumNameOrOptions]
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
> = PublicCompositeTypeNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      au_group_chapter_type: ["11", "7", "11-Subchapter-V"],
      au_group_job_status: ["pending", "running", "completed", "failed"],
      au_group_job_type: ["pacer_poll", "document_parse", "zoom_info_enrich", "salesforce_push"],
      au_group_schedule_f_status: [
        "monitoring",
        "detected",
        "pending_approval",
        "approved",
        "rejected",
        "processed",
      ],
    },
  },
} as const
