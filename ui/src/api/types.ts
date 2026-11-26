// The Marcarr API v1 contract (served under /api/v1). The backend
// (marcarr/routes/*.py) returns exactly these shapes; docs/API.md explains them.

export const STEPS = ['shots', 'subtitles', 'scenes', 'signals', 'cast', 'faces', 'tags'] as const;
export type Step = (typeof STEPS)[number];

/** done | rerun (an input changed) | failed | run (running) | queued | notrun |
 *  none (not supported here: no subtitles, no models) | off (turned off in Settings) */
export type StepState = 'done' | 'rerun' | 'failed' | 'run' | 'queued' | 'notrun' | 'none' | 'off';

export interface StepInfo {
  state: StepState;
  detail: string; // one line: "1,412 shots", "No subtitles in this file", the error
  seconds: number | null; // time the last run took
  ai_cost: number; // dollars spent by the last run
  finished_at: string | null;
  progress: number | null; // 0..1 while running
}

export type TagStatus = 'proposed' | 'accepted' | 'rejected';
export type Family =
  | 'place' | 'action' | 'beat' | 'mood' | 'occasion' | 'weather' | 'people' | 'creature' | 'content' | 'element';

/** What a title or video is doing, for the dot + one line under a poster. */
export interface StateLine {
  kind: 'done' | 'run' | 'notrun' | 'failed' | 'rerun' | 'queued';
  text: string; // "Analysed", "Analysing: scenes, step 3 of 7", "Failed at subtitles"
  progress: number | null; // 0..1 of the whole video while running
}

export interface TitleSummary {
  id: string; // movie:tmdb:671, show:tvdb:79168, episode:tvdb:79168:s01e02, plex:1234
  type: 'movie' | 'show' | 'episode';
  name: string;
  year: number | null;
  duration: number | null; // seconds (movies, episodes)
  poster: string | null; // URL to an image (served by Marcarr)
  videos: number;
  analysed: boolean;
  to_review: number; // proposed tags waiting
  steps: Record<Step, StepState> | null; // of the current video (null for shows)
  state: StateLine;
  episodes?: { total: number; analysed: number; seasons: number }; // shows only
  collection: string | null;
}

export interface Paged<T> {
  total: number;
  page?: number;
  items: T[];
}

export interface Person {
  id: string; // "ron-weasley"
  actor: string;
  character: string;
  photo: string | null;
  titles?: number; // titles they are in
}

export interface VideoSummary {
  id: string; // short content id, e.g. "7c9e21ab"
  edition: string;
  duration: number | null;
  steps_done: number;
  current: boolean;
  path: string;
}

export interface Title extends TitleSummary {
  summary: string;
  parent: { id: string; name: string } | null; // an episode's show
  season: number | null;
  episode: number | null;
  plex_key: string | null;
  tmdb_id: number | null;
  tvdb_id: number | null;
  video: Video | null; // the current video, with its steps
  all_videos: VideoSummary[];
  cast: Person[];
  seasons?: { season: number; episodes: number; analysed: number }[]; // shows
}

export interface Video {
  id: string;
  title: string; // title id
  title_name: string;
  edition: string;
  path: string;
  duration: number | null;
  width: number | null;
  height: number | null;
  size: number | null;
  steps: Record<Step, StepState>;
  step_info: Record<Step, StepInfo>;
  scenes: number;
  shots: number;
  lines: number;
  seconds_spent: number;
  ai_cost: number;
  to_review: number;
  state: StateLine;
  subtitles: { kind: string; detail: string } | null; // where the lines came from
}

export interface TagRef {
  id: string;
  tag: string; // vocab id: "christmas"
  name: string; // "Christmas"
  family: Family | null;
  status: TagStatus;
}

export interface Evidence {
  heard: string[];
  seen: string[];
}

export interface Tag extends TagRef {
  video: string;
  title: string;
  start: number;
  end: number;
  source: string; // "person", "ai", "fanscut", "doblarr", "mcp"
  source_detail: string; // "ai:claude/claude-sonnet-5-5"
  confidence: number | null;
  people: string[]; // person ids
  evidence: Evidence;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  n: number; // 1-based
  start: number;
  end: number;
  shots: number;
  people: string[]; // person ids seen or named in it
  tags: TagRef[]; // proposed and accepted (rejected left out)
  place: string | null; // named place id, e.g. "hogwarts/great-hall"
  place_name: string | null; // "Hogwarts › Great Hall"
  summary: string; // what happens (from the tagger), '' when unknown
  still: string; // URL of a frame from the middle
  spoiler: boolean;
  uncertain: boolean;
  to_review: number;
}

export interface Line {
  start: number;
  end: number;
  text: string;
}

export interface Face {
  id: string;
  video: string;
  person: string | null; // person id, null = unknown face
  at: number;
  score: number;
  box: [number, number, number, number] | null; // x, y, w, h in 0..1 of the frame
  confirmed: boolean | null; // true confirmed, false rejected, null unsure
  still: string; // URL of the face crop (or the frame)
}

export interface SceneDetail extends Scene {
  video: string;
  title: { id: string; name: string; year: number | null };
  duration: number | null;
  all_tags: Tag[]; // every tag overlapping the scene, rejected too
  lines: Line[];
  shot_cuts: number[]; // camera cut times inside and near the scene
  frames: { t: number; url: string }[]; // stills across the scene
  faces: Face[];
  cast: Person[];
  prev: number | null;
  next: number | null;
}

export interface Signal {
  signal: string; // dark, silence, loud, no-face, close-up ...
  start: number;
  end: number;
}

export interface AtTime {
  t: number;
  scene: number | null;
  people: string[];
  tags: { tag: string; name: string; status: TagStatus }[];
  place: string | null;
  signals: string[];
}

export interface VocabTag {
  id: string;
  name: string;
  family: Family;
  hint: string;
  see: string[];
  hear: string[];
  subjective: boolean;
  label: boolean; // written to Plex as a label
  off: boolean; // its family is off in Settings
  counts: { accepted: number; proposed: number; rejected: number };
}

export interface VocabFamily {
  family: Family;
  name: string; // "Occasion"
  subjective: boolean;
  off: boolean;
  tags: VocabTag[];
}

export interface Vocab {
  families: VocabFamily[];
  own: { id: string; name: string; hint: string }[]; // Marcarr's own: titles, theme, recap
  signals: { id: string; name: string; hint: string }[];
}

export interface ReviewItem extends Tag {
  title_name: string;
  year: number | null;
  scene: number | null;
  still: string;
  scene_summary: string;
}

export interface ReviewQueue {
  total: number;
  groups: { title: string; name: string; year: number | null; video: string; count: number; items: ReviewItem[] }[];
  facets: {
    families: Record<string, number>;
    sources: Record<string, number>;
    titles: { id: string; name: string; count: number }[];
  };
}

export interface SceneHit {
  title: string;
  title_name: string;
  year: number | null;
  video: string;
  scene: number;
  start: number;
  end: number;
  tags: TagRef[];
  summary: string;
  still: string;
  spoiler: boolean;
  line: string | null; // the matching dialogue line, for word searches
}

export interface Place {
  id: string; // "hogwarts/great-hall"
  name: string;
  inside: string | null; // parent place id
  franchise: string;
  implies: string[]; // vocab tag ids
  children: Place[];
  scenes: number;
  status: 'accepted' | 'proposed';
}

export interface ActivityRow {
  video: string;
  title: string;
  title_name: string;
  meta: string; // "2001 · 2h 32m"
  steps: Record<Step, StepState>;
  step_info: Record<Step, StepInfo>;
  seconds: number;
  ai_cost: number;
  state: StateLine;
}

export interface Activity {
  paused: boolean;
  running: { video: string; title_name: string; step: Step; step_index: number; progress: number | null; eta_seconds: number | null } | null;
  left: { videos: number; eta_seconds: number | null };
  month: { seconds: number; ai_cost: number; ai_limit: number; per_film_seconds: number | null; per_film_cost: number | null };
  rows: ActivityRow[];
  counts: Record<string, number>; // all, running, waiting, failed, done
}

export interface Status {
  version: string;
  queue: { running: number; waiting: number };
  ai: { enabled: boolean; month_cost: number; month_limit: number };
  plex: 'connected' | 'not set' | 'failing';
  review: number; // proposed tags in the library
  setup_done: boolean;
}

export interface ApiKey {
  id: string;
  name: string; // "FansCut"
  prefix: string; // first characters, the rest is hidden
  scopes: ('read' | 'propose' | 'review' | 'run')[];
  created_at: string;
  last_used: string | null;
  key?: string; // only right after creating it
}

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  enabled: boolean;
  state: 'working' | 'failing' | 'unused';
}

export interface WebhookCall {
  id: string;
  webhook: string;
  url: string;
  event: string;
  at: string;
  code: number | null;
  error: string;
}

/** Settings as GET /settings returns them; secrets come back masked ("••••"). */
export interface Settings {
  plex: { url: string; token: string; libraries: string[]; path_map: { from: string; to: string }[] };
  labels: { write: boolean; prefix: string; tags: string[] };
  ai: { enabled: boolean; model: string; vision_model: string; base_url: string; api_key: string; monthly_limit: number; auto_accept: number };
  tags: { families_off: string[]; search_closely: string[] };
  faces: { enabled: boolean; models: { name: string; present: boolean; size: number | null }[] };
  general: { theme: 'dark' | 'light' | 'system'; language: 'en' | 'es'; clock: '24h' | '12h' };
  analysis: { steps: Record<Step, boolean>; at_once: 1 | 2 | 4; window_start: string; window_end: string; on_new: boolean; transcribe: boolean };
  server: { require_key: boolean; data_dir: string };
}

export interface PlexLibrary {
  key: string;
  title: string;
  type: 'movie' | 'show';
  count: number | null;
}
