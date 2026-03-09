// Shared Supabase client — ES module, uses CDN ESM build
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm'

const SUPABASE_URL = 'https://psrbfzdsgpcuqokyqcso.supabase.co'
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBzcmJmemRzZ3BjdXFva3lxY3NvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc0NTA1MTIsImV4cCI6MjA4MzAyNjUxMn0.GuK5DW9LkNgFZJa64mFvv8syIP4OTvfcmwk2Fl6gKPE'

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
