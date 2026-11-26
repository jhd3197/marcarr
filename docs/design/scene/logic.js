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
    const START = 5390, END = 5587;
    // Sample review data. Sources and evidence are made up to show the layout; the dialogue is paraphrased, not the film's lines.
    const TAGS = [
      ['Christmas', 'AI', 'the words Christmas and presents', 'a Christmas tree, wrapped presents'],
      ['Magic', 'AI', 'invisibility cloak', 'a body that vanishes under a cloak'],
      ['Friendship', 'AI', '', 'two friends alone, laughing'],
      ['Happy', 'AI', '', 'smiling faces'],
      ['Snow', 'Doblarr', '', 'snow at the windows'],
      ['Bedroom', 'FansCut', '', 'four-poster beds'],
      ['Castle', '', '', '']
    ];
    const LINES = [
      [5398, [['Happy '], ['Christmas', 'Christmas'], [', Harry.']]],
      [5404, [['Why are you wearing that jumper?']]],
      [5409, [['Mum knits one every year. She sent you one too.']]],
      [5415, [['There are '], ['presents', 'Christmas'], [' for me?']]],
      [5462, [['That one has no name on it.']]],
      [5480, [['The note says it belonged to my father.']]],
      [5504, [["That's an "], ['invisibility cloak', 'Magic'], ['. They are really rare.']]]
    ];
    const FRAMES = [99, 100, 101, 102, 103, 101];   // stand-ins: the sheet has one still per scene, so neighbours fill the grid
    const dec = S.dec || {};
    const trim = S.trim || { s: START, e: END };
    const setDec = (name, v) => () => this.setState({ dec: { ...dec, [name]: v } });
    const setAll = (v) => () => { const d = { ...dec }; TAGS.forEach((t) => { if (t[1]) d[t[0]] = v; }); this.setState({ dec: d }); };
    const left = TAGS.filter((t) => t[1] && !dec[t[0]]).length;
    const face = S.face;
    const nudge = (k, d) => () => this.setState({ trim: { ...trim, [k]: trim[k] + d } });

    return {
      leftText: left ? left + ' to decide' : 'All decided',
      frames: FRAMES.map((n, i) => ({ at: hms(START + Math.round((END - START) * (i + 0.5) / 6)), aria: 'Frame ' + (i + 1) + ' of 6', bg: tileBg(n) + (i === 5 ? ';background-size:1400% 2100%' : '') })),
      trims: [['Start', 's', 5388], ['End', 'e', 5589]].map((t) => ({ name: t[0], at: hms(trim[t[1]]), back: nudge(t[1], -1), fwd: nudge(t[1], 1), snap: () => this.setState({ trim: { ...trim, [t[1]]: t[2] } }), backAria: t[0] + ' one second earlier', fwdAria: t[0] + ' one second later' })),
      lenText: ms(trim.e - trim.s) + ' long',
      lines: LINES.map((l) => ({ at: hms(l[0]), parts: l[1].map((p) => ({ t: p[0], s: p[1] ? 'border-radius:3px;padding:0 2px;font-weight:600;box-shadow:inset 0 -2px 0 ' + fvar(p[1]) + ';background:color-mix(in srgb,' + fvar(p[1]) + ' 22%,transparent)' : '' })) })),
      tags: TAGS.map((t) => {
        const v = t[1] ? dec[t[0]] : 'keep';
        const state = v === 'keep' ? 'accepted' : v === 'drop' ? 'rejected' : 'proposed';
        return {
          name: t[0], chip: chip(t[0], state), meta: (FAMOF[t[0]] ? FAMOF[t[0]].charAt(0).toUpperCase() + FAMOF[t[0]].slice(1) : '') + (t[1] ? ' · proposed by ' + t[1] : ' · kept by you'),
          hasHeard: !!t[2], heard: t[2], hasSeen: !!t[3], seen: t[3],
          open: state === 'proposed', closed: state !== 'proposed', canUndo: !!t[1],
          state: state === 'accepted' ? 'Accepted' : 'Rejected', stateStyle: 'font-size:12.5px;font-weight:600;color:' + (state === 'accepted' ? 'var(--ok)' : 'var(--faint)'),
          keep: setDec(t[0], 'keep'), drop: setDec(t[0], 'drop'), undo: setDec(t[0], undefined)
        };
      }),
      keepAll: setAll('keep'), dropAll: setAll('drop'),
      people: [
        { name: 'Harry', sub: 'Daniel Radcliffe as Harry Potter · 0.91', av: av('H', 44), unsure: false },
        { name: face === 'yes' ? 'Ron' : face === 'no' ? 'Not Ron' : 'Ron?', sub: face === 'yes' ? 'Rupert Grint as Ron Weasley · confirmed by you' : face === 'no' ? 'Face left without a name' : 'Rupert Grint as Ron Weasley · 0.38', av: av('R', 44) + (face ? '' : ';outline:2px dashed var(--warn);outline-offset:2px'), unsure: !face, yes: () => this.setState({ face: 'yes' }), no: () => this.setState({ face: 'no' }) }
      ]
    };
  }
}
</script>


</body></html>