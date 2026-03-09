-- =============================================================================
-- ImmoStage 3D — Database Schema
-- Supabase PostgreSQL (hosted)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- AGENTS — extends Supabase Auth users
-- One row per registered agent. Created via trigger or first login.
-- ---------------------------------------------------------------------------
CREATE TABLE agents (
  id           UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email        TEXT,
  full_name    TEXT,
  company      TEXT,
  plan         TEXT DEFAULT 'trial',       -- trial | starter | pro | agency
  watermark    BOOLEAN DEFAULT true,       -- show ImmoStage watermark on tours
  custom_logo  TEXT,                       -- URL to custom logo (pro+ only)
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- TOURS — one virtual property tour per listing
-- ---------------------------------------------------------------------------
CREATE TABLE tours (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id        UUID REFERENCES agents(id) ON DELETE CASCADE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  title           TEXT,                    -- e.g. "Maisonette Hamburg Altona"
  address         TEXT,                    -- display address for tour page
  floorplan_url   TEXT,                    -- uploaded floor plan image URL
  floorplan_w     INTEGER,                 -- floor plan image width (px)
  floorplan_h     INTEGER,                 -- floor plan image height (px)
  watermark       BOOLEAN DEFAULT true,    -- inherits from agent.watermark
  expires_at      TIMESTAMPTZ,            -- NULL = never expires
  view_count      INTEGER DEFAULT 0,
  last_viewed_at  TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- ROOMS — individual panoramas / rooms within a tour
-- Each room maps to one RunPod processing job.
-- ---------------------------------------------------------------------------
CREATE TABLE tour_rooms (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tour_id       UUID REFERENCES tours(id) ON DELETE CASCADE,
  agent_id      UUID REFERENCES agents(id) ON DELETE CASCADE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  name          TEXT,                      -- e.g. "Wohnzimmer", "Küche"

  -- Processing options
  mode          TEXT DEFAULT 'real',       -- real | staged | both
  style         TEXT,                      -- modern | scandinavian | luxury | ...
  prompt        TEXT,                      -- optional custom prompt override
  hotspot_x     NUMERIC,                   -- floor plan hotspot X (0-1 relative)
  hotspot_y     NUMERIC,                   -- floor plan hotspot Y (0-1 relative)

  -- Job state
  status        TEXT DEFAULT 'pending',    -- pending | uploading | processing | staging | fast_ready | complete | failed
  input_folder  TEXT,                      -- Supabase Storage path for input images
  error_msg     TEXT,                      -- human-readable error if status=error

  -- Output URLs (populated by RunPod worker on completion)
  panorama_url  TEXT,                      -- equirectangular panorama (real)
  depth_url     TEXT,                      -- depth map PNG
  splat_url     TEXT,                      -- Gaussian splat .ply / .splat file

  -- Billing & telemetry
  cost_usd      NUMERIC(6,4),             -- RunPod compute cost for this room
  processing_ms INTEGER                    -- wall-clock ms from trigger to done
);

-- ---------------------------------------------------------------------------
-- REALTIME — enable live status updates for UI polling
-- ---------------------------------------------------------------------------
ALTER PUBLICATION supabase_realtime ADD TABLE tour_rooms;
ALTER PUBLICATION supabase_realtime ADD TABLE tours;

-- ---------------------------------------------------------------------------
-- ROW LEVEL SECURITY
-- ---------------------------------------------------------------------------
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tours  ENABLE ROW LEVEL SECURITY;
ALTER TABLE tour_rooms  ENABLE ROW LEVEL SECURITY;

-- Agents: full access to own row only
CREATE POLICY "agents_own"
  ON agents FOR ALL
  USING (auth.uid() = id);

-- Tours: owner has full access, public can read (for shared tour links)
CREATE POLICY "tours_own"
  ON tours FOR ALL
  USING (auth.uid() = agent_id);

CREATE POLICY "tours_public_read"
  ON tours FOR SELECT
  USING (true);

-- Rooms: owner has full access, public can read (rooms load in tour viewer)
CREATE POLICY "tour_rooms_own"
  ON tour_rooms FOR ALL
  USING (auth.uid() = agent_id);

CREATE POLICY "tour_rooms_public_read"
  ON tour_rooms FOR SELECT
  USING (true);

-- ---------------------------------------------------------------------------
-- FUNCTIONS
-- ---------------------------------------------------------------------------

-- Increment view counter (called from edge function, bypasses RLS)
CREATE OR REPLACE FUNCTION increment_view_count(tour_id UUID)
RETURNS void AS $$
  UPDATE tours
  SET
    view_count     = view_count + 1,
    last_viewed_at = NOW()
  WHERE id = tour_id;
$$ LANGUAGE sql SECURITY DEFINER;

-- ---------------------------------------------------------------------------
-- STORAGE BUCKET — single "scans" bucket for all files
-- ---------------------------------------------------------------------------
-- All frontend + backend code uses bucket name "scans"
-- Path convention: scans/{room_id}/input/  — raw photos
--                  scans/{room_id}/        — panorama, depth, splat outputs

INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('scans', 'scans', true, 104857600)  -- 100MB limit
ON CONFLICT (id) DO NOTHING;

-- Allow authenticated users to upload to scans bucket
CREATE POLICY "scans_auth_upload"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'scans' AND auth.role() = 'authenticated');

-- Allow authenticated users to read their uploads
CREATE POLICY "scans_auth_read"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'scans');

-- Allow service role full access (for RunPod backend)
CREATE POLICY "scans_service_all"
  ON storage.objects FOR ALL
  USING (bucket_id = 'scans' AND auth.role() = 'service_role');
