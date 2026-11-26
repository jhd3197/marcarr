 data-dc-script="" data-props="{&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1180}}">
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
    // Sample queue. Times and costs are invented to show where they go.
    const ROWS = [
      ['cos', 'Chamber of Secrets', '2002 · 2h 54m', ['done', 'done', 'run', 'notrun', 'notrun', 'notrun', 'notrun'], '19 min', '$0.00', 'Running: scenes, 43%', 'Stop'],
      ['dh1', 'Deathly Hallows: Part 1', '2010 · 2h 26m', ['done', 'rerun', 'rerun', 'done', 'done', 'done', 'rerun'], '44 min', '$0.37', 'Needs a rerun: the subtitle file changed', 'Rerun 3 steps'],
      ['ootp', 'Order of the Phoenix', '2007 · 2h 18m', ['done', 'failed', 'notrun', 'done', 'done', 'notrun', 'notrun'], '21 min', '$0.00', 'Failed at subtitles: they are pictures, and reading them failed', 'Rerun subtitles'],
      ['dh2', 'Deathly Hallows: Part 2', '2011 · 2h 10m', all('notrun'), '', '', 'Not analysed', 'Analyse'],
      ['ss', "Sorcerer's Stone", '2001 · 2h 38m', all('done'), '47 min', '$0.41', 'Done', ''],
      ['poa', 'Prisoner of Azkaban', '2004 · 2h 21m', all('done'), '43 min', '$0.38', 'Done', ''],
      ['gof', 'Goblet of Fire', '2005 · 2h 37m', all('done'), '49 min', '$0.44', 'Done', ''],
      ['hbp', 'Half-Blood Prince', '2009 · 2h 33m', all('done'), '46 min', '$0.41', 'Done', '']
    ];
    // Sorcerer's Stone, step by step: 47 minutes in all
    const SS_STEPS = [['6m 10s', ''], ['0m 12s', ''], ['0m 41s', ''], ['9m 05s', ''], ['0m 04s', ''], ['14m 20s', ''], ['16m 28s', '$0.41: text $0.09, vision $0.32']];
    const kindOf = (st) => st.indexOf('failed') >= 0 || st.indexOf('rerun') >= 0 ? 'look' : st.indexOf('run') >= 0 ? 'running' : st.indexOf('notrun') >= 0 ? 'waiting' : 'done';
    const COLOR = { look: 'var(--warn)', running: 'var(--text)', waiting: 'var(--dim)', done: 'var(--dim)' };
    const f = S.f || 'all';
    const open = S.open === undefined ? 'ss' : S.open;
    const did = S.did || {};
    const rows = ROWS.map((r) => ({ r, kind: kindOf(r[3]) }));
    const filt = (key, name) => ({ name, n: key === 'all' ? rows.length : rows.filter((x) => x.kind === key).length, on: f === key, cls: 'pill' + (f === key ? ' on' : ''), pick: () => this.setState({ f: key }) });
    return {
      filters: [filt('all', 'All'), filt('running', 'Running'), filt('waiting', 'Waiting'), filt('look', 'Needs a look'), filt('done', 'Done')],
      stepNames: STEPS.map((s) => ({ name: s })),
      rows: rows.filter((x) => f === 'all' || x.kind === f).map((x) => {
        const r = x.r, queued = !!did[r[0]];
        return {
          title: 'Harry Potter and the ' + r[1], meta: r[2], open: open === r[0], toggle: () => this.setState({ open: open === r[0] ? '' : r[0] }),
          cells: r[3].map((st, i) => ({ style: cell(st), glyph: GLYPH[st] || '', label: STEPS[i] + ': ' + STATE[st] })),
          time: r[4], cost: r[5], state: queued ? 'Queued' : r[6],
          stateStyle: 'font-size:12.5px;font-weight:' + (x.kind === 'done' ? 500 : 600) + ';color:' + (queued ? 'var(--dim)' : r[3].indexOf('failed') >= 0 ? 'var(--bad)' : COLOR[x.kind]),
          hasAct: !!r[7] && !queued, actLabel: r[7], act: () => this.setState({ did: { ...did, [r[0]]: true } }),
          steps: STEPS.map((s, i) => ({ name: s, cell: cell(r[3][i]), glyph: GLYPH[r[3][i]] || '', state: STATE[r[3][i]], time: r[0] === 'ss' ? SS_STEPS[i][0] : '', cost: r[0] === 'ss' ? SS_STEPS[i][1] : '' }))
        };
      }),
      legend: ['done', 'run', 'rerun', 'failed', 'notrun', 'none', 'off'].map((k) => ({ name: STATE[k], style: cell(k), glyph: GLYPH[k] || '' }))
    };
  }
}
</script>


</body></html>