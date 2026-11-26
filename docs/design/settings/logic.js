 data-dc-script="" data-props="{&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:900}}">
class Component extends DCLogic {
  renderVals() {
    const S = this.state || {};
    const SHEET = '/_blob/a849bcffab7e01afcd7aa5209e7a04e5';
    const tileBg = (i) => 'background-image:url(' + SHEET + ');background-size:1000% 1500%;background-position:' + ((i % 10) / 9 * 100).toFixed(3) + '% ' + (Math.floor(i / 10) / 14 * 100).toFixed(3) + '%';
    const two = (n) => String(Math.floor(n)).padStart(2, '0');
    const hms = (s) => Math.floor(s / 3600) + ':' + two(s % 3600 / 60) + ':' + two(s % 60);
    const ms = (s) => Math.floor(s / 60) + ':' + two(s % 60);
    const FAM = [["Place","place",["Castle","School","Hospital","Prison","Church","Courtroom","Office","Bar or pub","Restaurant","Kitchen","Bedroom","Forest","Beach","Ocean","Desert","Mountains","City streets","Village","Train","Airplane","Spaceship","Underwater","Cave","Graveyard","Living room","Car"]],["Action","action",["Fight","Sword fight","Gunfight","Magic duel","Foot or animal chase","Car chase","Battle","Explosion","Escape","Heist","Rescue","Sports match","Race","Flying","Swimming","Training","Dancing","Singing","Sneaking","Transformation","Kidnapping","Interrogation","Phone call","Crying"]],["Beat","beat",["Arrival","Goodbye","Reunion","First meeting","Confession","Proposal","Kiss","Breakup","Death","Sacrifice","Betrayal","Planning","Flashback","Dream or vision","Montage","Speech","Revelation","Celebration","Meal","Journey","Argument","Apology"]],["Mood","mood",["Happy","Funny","Heartwarming","Romantic","Sad","Tense","Scary","Creepy","Epic","Triumphant","Peaceful","Nostalgic","Angry","Awkward","Mysterious","Bittersweet"]],["Occasion","occasion",["Christmas","Halloween","Thanksgiving","New Year","Easter","Valentine's Day","Birthday","Wedding","Funeral","Graduation","School dance","Party","Festival or fair","Summer holiday","Concert"]],["Weather","weather",["Snow","Rain","Thunderstorm","Fog","Heat","Wind"]],["Time of day","time",["Night","Sunrise","Sunset","Full moon"]],["People","people",["Family","Friendship","Romance","Rivalry","Mentor","Siblings","Parent and child","Children","Crowd","Alone"]],["Creature","creature",["Animal","Dog","Cat","Horse","Monster","Ghost","Robot"]],["Content","content",["Blood and gore","Nudity","Drug use","Strong language"]],["Element","element",["Magic","Fire","Water"]]];
    const FAMOF = {}; FAM.forEach((f) => f[2].forEach((t) => { FAMOF[t] = f[1]; }));
    const fvar = (t) => 'var(--f-' + (FAMOF[t] || 'place') + ')';
    const chip = (t, st) => 'display:inline-flex;align-items:center;height:24px;padding:0 9px 0 7px;border-radius:6px;box-sizing:border-box;font-size:12px;font-weight:600;white-space:nowrap;' + (st === 'proposed' ? 'border:1.5px dashed ' + fvar(t) + ';color:var(--text)' : st === 'rejected' ? 'border:1px solid var(--line);color:var(--faint);text-decoration:line-through' : 'border-left:4px solid ' + fvar(t) + ';background:var(--raised);color:var(--text)') + (FAMOF[t] === 'mood' ? ';font-weight:500' : '');
    const PEOPLE = { H: ['Harry', 'Harry Potter', 'Daniel Radcliffe', '/_blob/70d060bde9fab0d8d0f85f8fb858e65a'], R: ['Ron', 'Ron Weasley', 'Rupert Grint', '/_blob/209f0a12d6085c8461342bd41d18cd4b'], G: ['Hermione', 'Hermione Granger', 'Emma Watson', '/_blob/a0163672bf8bbb37c1815479eba67547'], A: ['Hagrid', 'Rubeus Hagrid', 'Robbie Coltrane', ''] };
    const av = (k, size) => 'flex:none;display:inline-flex;align-items:center;justify-content:center;width:' + size + 'px;height:' + size + 'px;border-radius:50%;font:700 ' + Math.round(size * 0.45) + 'px DM Sans,sans-serif;color:var(--text);background:var(--hover)' + (PEOPLE[k] && PEOPLE[k][3] ? ' url(' + PEOPLE[k][3] + ') center/cover' : '');
    const STEPS = ['shots', 'subtitles', 'scenes', 'signals', 'cast', 'faces', 'tags'];
    const STATE = { done: 'Done', rerun: 'Needs a rerun', failed: 'Failed', run: 'Running', notrun: 'Not run', none: 'Not supported here', off: 'Off' };
    const GLYPH = { done: '\u2713', rerun: '\u21bb', failed: '\u00d7', none: '/', off: '\u2013' };
    const CELLS = { done: 'background:var(--ok);color:var(--bg)', rerun: 'border:2px solid var(--warn);color:var(--warn)', failed: 'background:var(--bad);color:var(--bg)', run: 'background:linear-gradient(90deg,var(--accent) 55%,var(--border) 55%)', notrun: 'border:1.5px dashed var(--faint)', none: 'background:var(--raised);color:var(--faint)', off: 'border:1px solid var(--border);color:var(--faint)' };
    const cell = (st) => 'flex:none;display:inline-flex;align-items:center;justify-content:center;width:30px;height:18px;border-radius:4px;box-sizing:border-box;font:700 12px DM Mono,monospace;' + CELLS[st];
    const libs = S.libs || { Movies: true, 'TV Shows': true };
    const ai = S.ai !== false, labels = S.labels !== false;
    const got = S.got || { 'Face detection': true };
    const famOff = S.famOff || { content: true };
    const labelTags = S.labelTags || ['Christmas', 'Halloween', 'Snow'];
    const sec = S.sec || 'general';
    // Sample apps and last-call times
    const APPS = [['FansCut', 'App', 'Last called 2 minutes ago', '#00aeef', ['read', 'propose', 'run']], ['Doblarr', 'App', 'Last called yesterday', '#ff8f73', ['read', 'propose']], ['Assistant', 'MCP client', 'Never called', '#929a9d', ['read', 'propose']]];
    const MODELS = ['Face detection', 'Face matching'];
    const SECS = [['general', 'General'], ['plex', 'Plex'], ['labels', 'Plex labels'], ['analysis', 'Analysis'], ['ai', 'AI'], ['tags', 'Tags'], ['faces', 'Faces'], ['places', 'Named places'], ['apps', 'Connected apps'], ['notify', 'Notifications'], ['backup', 'Backup and About']];
    const set = (patch) => this.setState({ ...patch, dirty: true });
    const show = {};
    SECS.forEach((s) => { show[s[0]] = sec === s[0]; });
    const dirty = !!S.dirty;
    const theme = S.theme || 'System', clock = S.clock || '24-hour', when = S.when || 'Always';
    const stepOff = S.stepOff || {};
    const srcOff = S.srcOff || {};
    const seg = (list, cur, key) => list.map((n) => ({ name: n, on: cur === n, pick: () => set({ [key]: n }) }));
    const WHAT = { shots: 'Camera cuts', subtitles: 'Dialogue lines', scenes: 'Shots grouped into scenes', signals: 'Dark, silence, loud and the rest', cast: 'Actors and characters', faces: 'Who is on screen', tags: 'What each scene is' };
    const HOOKS = [['http://fanscut.local/hooks/marcarr', ['video.analysed', 'tag.kept', 'tag.dropped'], true], ['http://doblarr.local/hooks/marcarr', ['step.finished'], false]];
    const LOG = [['01:02', 'step.finished', HOOKS[1][0], 500], ['01:02', 'step.finished', HOOKS[1][0], 500], ['00:47', 'tag.kept', HOOKS[0][0], 200], ['00:31', 'video.analysed', HOOKS[0][0], 200]];
    return {
      themes: seg(['System', 'Dark', 'Light'], theme, 'theme'), clocks: seg(['24-hour', '12-hour'], clock, 'clock'), whens: seg(['Always', 'Only at night'], when, 'when'), atNight: when === 'Only at night',
      steps: STEPS.map((n) => { const note = n === 'tags' && !ai ? 'Needs AI' : n === 'faces' && MODELS.some((m) => !got[m]) ? 'Needs the face models' : ''; return { name: n, what: WHAT[n], on: !stepOff[n], aria: 'Run ' + n, hasNote: !!note, note, toggle: () => set({ stepOff: { ...stepOff, [n]: !stepOff[n] } }) }; }),
      auto: S.auto !== false, toggleAuto: () => set({ auto: S.auto === false }),
      placesWaiting: '3 to review',
      sources: ['Dialogue', 'Reference stills'].map((n) => ({ name: n, on: !srcOff[n], toggle: () => set({ srcOff: { ...srcOff, [n]: !srcOff[n] } }) })),
      imported: !!S.imported, importWiki: () => this.setState({ imported: true }),
      hooks: HOOKS.map((h) => ({ url: h[0], events: h[1], state: h[2] ? 'Working' : 'Failing', stateStyle: 'flex:0 0 60px;font-size:12.5px;font-weight:600;color:' + (h[2] ? 'var(--ok)' : 'var(--bad)') })),
      log: LOG.map((d) => ({ at: d[0], event: d[1], url: d[2], code: d[3], failed: d[3] !== 200, codeStyle: 'flex:0 0 36px;font-weight:500;color:' + (d[3] === 200 ? 'var(--ok)' : 'var(--bad)') })),
      dirty, saveLabel: dirty ? 'Save changes' : 'Saved', saveCls: dirty ? 'btn pri' : 'btn',
      save: () => this.setState({ dirty: false }),
      discard: () => this.setState({ libs: undefined, ai: undefined, labels: undefined, famOff: undefined, labelTags: undefined, theme: undefined, clock: undefined, when: undefined, stepOff: undefined, srcOff: undefined, auto: undefined, dirty: false }),
      secs: SECS.map((s) => ({ name: s[1], on: sec === s[0], pick: () => this.setState({ sec: s[0] }) })),
      show,
      libs: Object.keys(libs).map((k, i) => ({ k: i ? '' : 'Libraries', name: k, on: libs[k], note: !libs[k] ? '' : k === 'Movies' ? '8 films' : '1 show, 236 episodes', aria: 'Include ' + k, toggle: () => set({ libs: { ...libs, [k]: !libs[k] } }) })),
      labels, toggleLabels: () => set({ labels: !labels }),
      labelTags: labelTags.map((t) => ({ label: 'marcarr:' + t.toLowerCase(), aria: 'Stop writing ' + t, remove: () => set({ labelTags: labelTags.filter((x) => x !== t) }) })),
      addLabel: () => { const next = ['Rain', 'Night', 'Birthday'].find((t) => labelTags.indexOf(t) < 0); if (next) set({ labelTags: labelTags.concat([next]) }); },
      ai, noAi: !ai, toggleAi: () => set({ ai: !ai }),
      families: FAM.map((f) => ({ name: f[0], on: !famOff[f[1]], count: f[2].length + ' tags', subjective: f[1] === 'mood', aria: 'Look for ' + f[0] + ' tags', bar: 'flex:none;width:6px;height:20px;border-radius:3px;background:var(--f-' + f[1] + ')', toggle: () => set({ famOff: { ...famOff, [f[1]]: !famOff[f[1]] } }) })),
      models: MODELS.map((m) => ({ name: m, missing: !got[m], state: got[m] ? 'Downloaded' : 'Not downloaded', stateStyle: 'font-size:13px;font-weight:600;color:' + (got[m] ? 'var(--ok)' : 'var(--warn)'), get: () => this.setState({ got: { ...got, [m]: true } }) })),
      facesOff: MODELS.some((m) => !got[m]),
      apps: APPS.map((a) => ({ name: a[0], kind: a[1], last: a[2], scopes: a[4], initial: a[0].charAt(0), badge: 'flex:none;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:7px;font:700 13px Outfit,sans-serif;color:#101317;background:' + a[3] }))
    };
  }
}
</script>


</body></html>