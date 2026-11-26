 data-dc-script="" data-props="{&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1000}}">
class Component extends DCLogic {
  renderVals() {
    const S = this.state || {};
    const SHEET = '/_blob/a849bcffab7e01afcd7aa5209e7a04e5';
    const tileBg = (i) => 'background-image:url(' + SHEET + ');background-size:1000% 1500%;background-position:' + ((i % 10) / 9 * 100).toFixed(3) + '% ' + (Math.floor(i / 10) / 14 * 100).toFixed(3) + '%';
    const two = (n) => String(Math.floor(n)).padStart(2, '0');
    const hms = (s) => Math.floor(s / 3600) + ':' + two(s % 3600 / 60) + ':' + two(s % 60);
    const ms = (s) => Math.floor(s / 60) + ':' + two(s % 60);
    const FAM = [["Place","place",["Castle","School","Hospital","Prison","Church","Courtroom","Office","Bar or pub","Restaurant","Kitchen","Bedroom","Forest","Beach","Ocean","Desert","Mountains","City streets","Village","Train","Airplane","Spaceship","Underwater","Cave","Graveyard"]],["Action","action",["Fight","Sword fight","Gunfight","Magic duel","Chase","Car chase","Battle","Explosion","Escape","Heist","Rescue","Sports match","Race","Flying","Swimming","Training","Dancing","Singing","Sneaking","Transformation","Kidnapping","Interrogation"]],["Beat","beat",["Arrival","Goodbye","Reunion","First meeting","Confession","Proposal","Kiss","Breakup","Death","Sacrifice","Betrayal","Planning","Flashback","Dream or vision","Montage","Speech","Revelation","Celebration","Meal","Journey"]],["Mood","mood",["Happy","Funny","Heartwarming","Romantic","Sad","Tense","Scary","Creepy","Epic","Triumphant","Peaceful","Nostalgic","Angry","Awkward","Mysterious","Bittersweet"]],["Occasion","occasion",["Christmas","Halloween","Thanksgiving","New Year","Easter","Valentine's Day","Birthday","Wedding","Funeral","Graduation","School dance","Party","Festival or fair","Summer holiday"]],["Weather","weather",["Snow","Rain","Thunderstorm","Fog","Sunrise","Sunset","Night","Full moon","Heat","Wind"]],["People","people",["Family","Friendship","Romance","Rivalry","Mentor","Siblings","Parent and child","Children","Crowd","Alone"]],["Creature","creature",["Animal","Dog","Cat","Horse","Monster","Ghost","Robot","Magic"]],["Content","content",["Blood and gore","Nudity","Drug use","Strong language"]],["Element","element",["Fire","Water"]]];
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
    const all = (st) => STEPS.map(() => st);
    // [key, title, year, length, colour, frame, the seven steps, tags to review, note]. States are samples, one per situation in the brief.
    const FILMS = [
      ['ss', "Sorcerer's Stone", 2001, '2h 38m', '#d3a85a', '/_blob/4a9ff806b2166895ad35637e33ae971c', all('done'), 108],
      ['cos', 'Chamber of Secrets', 2002, '2h 54m', '#6fa36a', '/_blob/6bac9bf258399df194b54b09fa3ccc76', ['done', 'done', 'run', 'notrun', 'notrun', 'notrun', 'notrun'], 0],
      ['poa', 'Prisoner of Azkaban', 2004, '2h 21m', '#5b93c7', '/_blob/feb3887babd67462e3d586f3ddda6c75', all('done'), 0],
      ['gof', 'Goblet of Fire', 2005, '2h 37m', '#9a86d6', '/_blob/b39aa73727eff713887e1fdf0a98d097', all('done'), 0],
      ['ootp', 'Order of the Phoenix', 2007, '2h 18m', '#47b3ad', '/_blob/32e9e5d90a8fe37097c568a702f0dbb0', ['done', 'failed', 'notrun', 'done', 'done', 'notrun', 'notrun'], 0],
      ['hbp', 'Half-Blood Prince', 2009, '2h 33m', '#c27a5c', '/_blob/b10b9cad2713b3a32173934846b5bb66', all('done'), 0],
      ['dh1', 'Deathly Hallows: Part 1', 2010, '2h 26m', '#b5b9c2', '/_blob/10ca62bfc9fd5dfbfda86baac4ef2e1f', ['done', 'rerun', 'rerun', 'done', 'done', 'done', 'rerun'], 5],
      ['dh2', 'Deathly Hallows: Part 2', 2011, '2h 10m', '#d98fb0', '', all('notrun'), 0],
      ['fr', 'Friends', 1994, '10 seasons · 236 episodes', '#9a86d6', '', ['done', 'done', 'done', 'done', 'done', 'run', 'notrun'], 14, 'show']
    ];
    const kindOf = (st) => st.indexOf('failed') >= 0 ? 'failed' : st.indexOf('rerun') >= 0 ? 'rerun' : st.indexOf('run') >= 0 ? 'run' : st.indexOf('notrun') >= 0 ? 'notrun' : 'done';
    const TEXT = { done: 'Analysed', run: 'Analysing: scenes, step 3 of 7', notrun: 'Not analysed', failed: 'Failed at subtitles', rerun: 'Needs a rerun' };
    const DOT = { done: 'var(--ok)', run: 'var(--accent)', notrun: 'var(--faint)', failed: 'var(--bad)', rerun: 'var(--warn)' };
    const view = S.view || 'grid', f = S.f || 'all', name = (S.name || '').toLowerCase();
    const rows = FILMS.map((x) => ({ x, kind: kindOf(x[6]), show: x[8] === 'show', title: x[8] === 'show' ? x[1] : 'Harry Potter and the ' + x[1] }));
    const match = { all: () => true, movies: (r) => !r.show, shows: (r) => r.show, analysed: (r) => r.kind === 'done', review: (r) => r.x[7] > 0, failed: (r) => r.kind === 'failed' };
    const shown = rows.filter((r) => match[f](r) && r.title.toLowerCase().indexOf(name) >= 0);
    const filt = (key, label) => ({ name: label, n: rows.filter(match[key]).length, on: f === key, cls: 'pill' + (f === key ? ' on' : ''), pick: () => this.setState({ f: key }) });

    return {
      isGrid: view === 'grid', isList: view === 'list', showGrid: () => this.setState({ view: 'grid' }), showList: () => this.setState({ view: 'list' }),
      onName: (e) => this.setState({ name: e && e.target ? e.target.value : '' }),
      notRun: rows.filter((r) => r.kind === 'notrun').length,
      filters: [filt('all', 'All'), filt('movies', 'Movies'), filt('shows', 'Shows'), filt('analysed', 'Analysed'), filt('review', 'Waiting for review'), filt('failed', 'Failed')],
      stepNames: STEPS.map((s) => ({ name: s })),
      films: shown.map((r) => {
        const x = r.x;
        return {
          short: x[1], title: r.title, meta: x[2] + ' · ' + x[3], href: x[0] === 'ss' ? 'Title.dc.html' : r.show ? 'Show.dc.html' : '#',
          poster: 'background:linear-gradient(180deg,rgba(0,0,0,0) 45%,rgba(0,0,0,.88))' + (x[5] ? ',url(' + x[5] + ') center/cover' : '') + ',color-mix(in srgb,' + x[4] + ' 55%,#171b20)' + (r.kind === 'notrun' ? ';filter:saturate(.35)' : ''),
          hasReview: x[7] > 0, review: x[7], reviewAria: x[7] + ' tags to review', reviewText: x[7] ? x[7] : '',
          running: r.kind === 'run', bar: 'display:block;height:100%;width:' + (r.show ? 26 : 43) + '%;background:#f5d547',
          stateText: r.show ? '62 of 236 episodes analysed' : TEXT[r.kind], dot: 'flex:none;width:8px;height:8px;border-radius:50%;background:' + DOT[r.kind],
          cells: x[6].map((st, i) => ({ style: cell(st), glyph: GLYPH[st] || '', label: STEPS[i] + ': ' + STATE[st] }))
        };
      }),
      empty: shown.length === 0, emptyText: f === 'shows' ? 'No shows in the libraries Marcarr looks at. Add a library in Settings.' : 'Nothing matches.'
    };
  }
}
</script>


</body></html>