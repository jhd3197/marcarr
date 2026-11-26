// One function per Marcarr API call. Pages import from here, never fetch directly.
import type {
  Activity, ApiKey, AtTime, Collection, CustomTag, CustomTagBody, CutKind, CutRange, TitleCuts, Face, Line, Paged, Person, Place, PlexLibrary, ReviewItem, ReviewQueue, CharacterGraph,
  Scene, SceneDetail, SceneHit, Settings, Signal, Status, Step, Tag, Title, TitleSummary, Video,
  Vocab, Webhook, WebhookCall,
} from './types';

export const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Query = Record<string, string | number | boolean | undefined | null | string[]>;

export function qs(q?: Query): string {
  if (!q) return '';
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === '') continue;
    p.set(k, Array.isArray(v) ? v.join(',') : String(v));
  }
  const s = p.toString();
  return s ? '?' + s : '';
}

async function req<T>(method: string, path: string, body?: unknown, q?: Query): Promise<T> {
  const res = await fetch(BASE + path + qs(q), {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail || j.error || msg;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T,>(path: string, q?: Query) => req<T>('GET', path, undefined, q);
const post = <T,>(path: string, body?: unknown, q?: Query) => req<T>('POST', path, body ?? {}, q);
const put = <T,>(path: string, body: unknown) => req<T>('PUT', path, body);
const patch = <T,>(path: string, body: unknown) => req<T>('PATCH', path, body);
const del = <T,>(path: string) => req<T>('DELETE', path);

const enc = encodeURIComponent;

// -- URLs (images, clips) ----------------------------------------------------------
export const urls = {
  poster: (title: string, width = 300) => `${BASE}/titles/${enc(title)}/poster?width=${width}`,
  frame: (video: string, t: number, h = 240) => `${BASE}/videos/${video}/frame.jpg?t=${t.toFixed(2)}&h=${h}`,
  still: (video: string, scene: number) => `${BASE}/videos/${video}/scenes/${scene}/still.jpg`,
  clip: (video: string, from: number, to: number) => `${BASE}/videos/${video}/clip.mp4?from=${from.toFixed(2)}&to=${to.toFixed(2)}`,
  analysis: (video: string) => `${BASE}/videos/${video}/analysis`,
  personPhoto: (person: string) => `${BASE}/people/${enc(person)}/photo`,
  face: (face: string) => `${BASE}/faces/${face}/crop.jpg`,
  backup: () => `${BASE}/backup/export`,
  logs: () => `${BASE}/logs`,
};

// -- system ------------------------------------------------------------------------
export const api = {
  status: () => get<Status>('/status'),
  settings: () => get<Settings>('/settings'),
  saveSettings: (s: Partial<Settings>) => put<Settings>('/settings', s),
  testPlex: (url: string, token: string) => post<{ ok: boolean; name: string; libraries: PlexLibrary[]; error?: string }>('/settings/plex/test', { url, token }),
  plexLibraries: () => get<PlexLibrary[]>('/plex/libraries'),
  scanLibrary: () => post<{ queued: boolean; job: string }>('/library/scan'),
  finishSetup: () => post<Status>('/setup/done'),
  downloadFaceModels: () => post<{ queued: boolean; job: string }>('/faces/models/download'),
  writeLabels: () => post<{ queued: boolean; job: string }>('/plex/labels'),
  importBackup: (doc: unknown) => post<{ imported: Record<string, number> }>('/backup/import', doc),

  // -- titles and videos -------------------------------------------------------------
  titles: (q: { type?: string; analysed?: boolean; q?: string; filter?: string; page?: number; per_page?: number; parent?: string; season?: number } = {}) =>
    get<Paged<TitleSummary> & { counts: Record<string, number> }>('/titles', q),
  title: (id: string) => get<Title>(`/titles/${enc(id)}`),
  graph: (id: string, q: { video?: string; through?: number | null } = {}) =>
    get<CharacterGraph>(`/titles/${enc(id)}/graph`, { video: q.video, through: q.through ?? undefined }),
  runTitle: (id: string, steps?: Step[]) => post<{ queued: number }>(`/titles/${enc(id)}/run`, { steps }),
  cuts: (id: string) => get<TitleCuts>(`/titles/${enc(id)}/cuts`),
  markCut: (id: string, body: { edition: string; base?: string; kind?: CutKind; video?: string | null; start?: number | null; end?: number | null; note?: string }) =>
    post<CutRange>(`/titles/${enc(id)}/cuts`, body),
  editCut: (cut: string, body: Partial<Pick<CutRange, 'status' | 'start' | 'end' | 'note' | 'edition' | 'base' | 'kind'>>) => patch<CutRange>(`/cuts/${cut}`, body),
  deleteCut: (cut: string) => del<{ deleted: string }>(`/cuts/${cut}`),
  keepCuts: (id: string, source?: string) => post<{ kept: number }>(`/titles/${enc(id)}/cuts/keep`, { source }),
  compareVersions: (id: string, a?: string, b?: string) => post<{ id: string }>(`/titles/${enc(id)}/cuts/compare`, { a, b }),
  researchCuts: (id: string) => post<{ id: string }>(`/titles/${enc(id)}/cuts/research`),
  video: (id: string) => get<Video>(`/videos/${id}`),
  runVideo: (id: string, steps?: Step[]) => post<{ queued: boolean; position: number }>(`/videos/${id}/run`, { steps }),
  scenes: (video: string, q: { from?: number; to?: number; tag?: string; review?: boolean } = {}) =>
    get<Paged<Scene>>(`/videos/${video}/scenes`, q),
  scene: (video: string, n: number) => get<SceneDetail>(`/videos/${video}/scenes/${n}`),
  sceneBrief: (video: string, n: number, link?: string) => get<{ text: string }>(`/videos/${video}/scenes/${n}/brief`, { link }),
  moveScene: (video: string, n: number, body: { start?: number; end?: number; snap?: boolean }) =>
    patch<SceneDetail>(`/videos/${video}/scenes/${n}`, body),
  at: (video: string, t: number) => get<AtTime>(`/videos/${video}/at/${t}`),
  lines: (video: string, q: { from?: number; to?: number } = {}) => get<Paged<Line>>(`/videos/${video}/lines`, q),
  signals: (video: string, signal?: string) => get<Paged<Signal>>(`/videos/${video}/signals`, { signal }),
  faces: (video: string, q: { person?: string; confirmed?: boolean } = {}) => get<Paged<Face>>(`/videos/${video}/faces`, q),
  videoTags: (video: string, q: { status?: string; family?: string; source?: string } = {}) =>
    get<Paged<Tag>>(`/videos/${video}/tags`, q),
  proposeTag: (video: string, body: { tag: string; start: number; end: number; people?: string[]; status?: 'proposed' | 'accepted'; evidence?: { heard?: string[]; seen?: string[] }; summary?: string }) =>
    post<Tag>(`/videos/${video}/tags`, body),

  // -- tags --------------------------------------------------------------------------
  vocab: (q: { family?: string; used?: boolean } = {}) => get<Vocab>('/tags', q),
  keep: (id: string) => post<Tag>(`/tags/${id}/keep`),
  drop: (id: string) => post<Tag>(`/tags/${id}/drop`),
  undo: (id: string) => post<Tag>(`/tags/${id}/undo`),
  editTag: (id: string, body: { start?: number; end?: number; people?: string[]; tag?: string }) => patch<Tag>(`/tags/${id}`, body),
  deleteTag: (id: string) => del<void>(`/tags/${id}`),
  bulk: (ids: string[], action: 'keep' | 'drop' | 'undo') => post<{ changed: number }>('/tags/bulk', { ids, action }),
  setTagLabel: (tag: string, label: boolean) => post<{ tag: string; label: boolean }>(`/tags/${enc(tag)}/label`, { label }),
  // custom tags ("My tags"). Removing one that is on any scene retires it instead.
  addCustomTag: (body: CustomTagBody & { name: string; id?: string }) => post<CustomTag>('/tags/mine', body),
  editCustomTag: (id: string, body: CustomTagBody) => patch<CustomTag>(`/tags/mine/${enc(id)}`, body),
  deleteCustomTag: (id: string) => del<{ deleted: boolean; retired: boolean; tag: CustomTag | null }>(`/tags/mine/${enc(id)}`),

  // -- review and search -------------------------------------------------------------
  review: (q: { family?: string; source?: string; title?: string; page?: number; per_page?: number } = {}) =>
    get<ReviewQueue>('/review', q),
  reviewItems: (q: { family?: string; source?: string; title?: string; after?: string; limit?: number } = {}) =>
    get<Paged<ReviewItem>>('/review/items', q),
  // status: accepted (kept), proposed (kept and waiting for review), review (waiting only)
  // signals: measured signal ids; each must cover at least half of a scene
  search: (q: { tags?: string[]; person?: string; q?: string; signals?: string[]; status?: 'accepted' | 'proposed' | 'review'; title?: string; page?: number } = {}) =>
    get<Paged<SceneHit>>('/search/scenes', q),
  // collections: saved searches, each with how many kept scenes match now
  collections: () => get<Paged<Collection>>('/collections'),
  addCollection: (body: { name: string; tags?: string[]; person?: string | null; q?: string; signals?: string[] }) => post<Collection>('/collections', body),
  renameCollection: (id: string, name: string) => patch<Collection>(`/collections/${id}`, { name }),
  deleteCollection: (id: string) => del<void>(`/collections/${id}`),

  // -- people, faces, places ---------------------------------------------------------
  people: (q: { title?: string; q?: string } = {}) => get<Paged<Person>>('/people', q),
  person: (id: string) => get<Person & { titles_in: { id: string; name: string; year: number | null; scenes: number }[]; faces_to_confirm: number; scene_count: number }>(`/people/${enc(id)}`),
  personScenes: (id: string, title?: string) => get<Paged<SceneHit>>(`/people/${enc(id)}/scenes`, { title }),
  personFaces: (id: string, confirmed?: boolean) => get<Paged<Face>>(`/people/${enc(id)}/faces`, { confirmed }),
  confirmFace: (id: string) => post<Face>(`/faces/${id}/confirm`),
  rejectFace: (id: string) => post<Face>(`/faces/${id}/reject`),
  assignFace: (id: string, person: string) => post<Face>(`/faces/${id}/assign`, { person }),
  bulkFaces: (ids: string[], action: 'confirm' | 'reject') => post<{ changed: number }>('/faces/bulk', { ids, action }),
  places: (franchise?: string) => get<{ franchises: { name: string; titles: number; places: number }[]; items: Place[] }>('/places', { franchise }),
  place: (id: string) => get<Place & { path: { id: string; name: string }[] }>(`/places/${id}`),
  placeScenes: (id: string) => get<Paged<SceneHit>>(`/places/${id}/scenes`),
  addPlace: (body: { name: string; inside?: string | null; franchise: string; implies?: string[] }) => post<Place>('/places', body),
  editPlace: (id: string, body: { name?: string; implies?: string[] }) => patch<Place>(`/places/${id}`, body),
  deletePlace: (id: string) => del<void>(`/places/${id}`),
  setScenePlace: (video: string, n: number, place: string | null) => post<Scene>(`/videos/${video}/scenes/${n}/place`, { place }),

  // -- activity ----------------------------------------------------------------------
  activity: (filter?: string) => get<Activity>('/activity', { filter }),
  analyseLeft: () => post<{ queued: number }>('/activity/analyse'),
  pause: () => post<Activity>('/activity/pause'),
  resume: () => post<Activity>('/activity/resume'),

  // -- connected apps and webhooks ---------------------------------------------------
  keys: () => get<ApiKey[]>('/keys'),
  addKey: (name: string, scopes: ApiKey['scopes']) => post<ApiKey>('/keys', { name, scopes }),
  renewKey: (id: string) => post<ApiKey>(`/keys/${id}/renew`),
  deleteKey: (id: string) => del<void>(`/keys/${id}`),
  webhooks: () => get<Webhook[]>('/webhooks'),
  addWebhook: (url: string, events: string[]) => post<Webhook>('/webhooks', { url, events }),
  editWebhook: (id: string, body: { url?: string; events?: string[]; enabled?: boolean }) => patch<Webhook>(`/webhooks/${id}`, body),
  deleteWebhook: (id: string) => del<void>(`/webhooks/${id}`),
  testWebhook: (id: string) => post<WebhookCall>(`/webhooks/${id}/test`),
  webhookCalls: () => get<WebhookCall[]>('/webhooks/calls'),
  resendCall: (id: string) => post<WebhookCall>(`/webhooks/calls/${id}/resend`),
  events: () => get<{ name: string; what: string; example: unknown }[]>('/events'),
};

/** The search page showing a collection's kept scenes (the scenes its count counts). */
export function collectionHref(c: Pick<Collection, 'tags' | 'person' | 'q' | 'signals'>): string {
  return '/search' + qs({ tags: c.tags, person: c.person, q: c.q, signals: c.signals, proposed: '0' });
}

/** For a call not listed above yet: add it to `api` when the endpoint is settled. */
export const raw = { get, post, put, patch, del };
