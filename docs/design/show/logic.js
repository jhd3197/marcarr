 data-dc-script="" data-props="{&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1400}}">
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
    const COUNT = [24, 24, 25, 24, 24, 25, 24, 24, 24, 18];
    // Season 1. Titles are from memory, so check them. Tags and review counts are samples: [title, tags, proposed?, to review]
    const S1 = [['The Pilot', ['Wedding'], 1, 3], ['The One with the Sonogram at the End', [], 0, 0], ['The One with the Thumb', [], 0, 0], ['The One with George Stephanopoulos', ['Night'], 0, 0], ['The One with the East German Laundry Detergent', [], 0, 0], ['The One with the Butt', [], 0, 0], ['The One with the Blackout', ['Night'], 0, 0], ['The One Where Nana Dies Twice', ['Funeral', 'Hospital'], 0, 0], ['The One Where Underdog Gets Away', ['Thanksgiving'], 0, 0], ['The One with the Monkey', ['New Year', 'Animal'], 0, 0], ['The One with Mrs. Bing', [], 0, 0], ['The One with the Dozen Lasagnas', [], 0, 0], ['The One with the Boobies', [], 0, 0], ['The One with the Candy Hearts', ["Valentine's Day"], 1, 2], ['The One with the Stoned Guy', ['Restaurant'], 0, 0], ['The One with Two Parts: Part 1', [], 0, 0], ['The One with Two Parts: Part 2', ['Hospital'], 0, 0], ['The One with All the Poker', [], 0, 0], ['The One Where the Monkey Gets Away', ['Animal'], 0, 0], ['The One with the Evil Orthodontist', [], 0, 0], ['The One with the Fake Monica', [], 0, 0], ['The One with the Ick Factor', [], 0, 0], ['The One with the Birth', ['Hospital'], 0, 0], ['The One Where Rachel Finds Out', ['Birthday'], 1, 9]];
    const stateOf = (s, e) => s < 3 ? 'done' : s === 3 ? (e <= 14 ? 'done' : e === 15 ? 'run' : 'notrun') : 'notrun';
    const COL = { done: 'background:var(--ok)', run: 'background:var(--accent)', notrun: 'border:1.5px dashed var(--faint)' };
    const WORD = { done: 'Analysed', run: 'Analysing: faces, step 6 of 7', notrun: 'Not analysed' };
    const sn = S.sn || 1;
    return {
      seasons: COUNT.map((n, i) => {
        const s = i + 1, eps = Array.from({ length: n }, (x, k) => stateOf(s, k + 1));
        return { name: 'Season ' + s, on: sn === s, pick: () => this.setState({ sn: s }), count: eps.filter((x) => x === 'done').length + ' of ' + n, cells: eps.map((st) => 'width:11px;height:11px;border-radius:3px;box-sizing:border-box;' + COL[st]) };
      }),
      seasonTitle: 'Season ' + sn,
      episodes: Array.from({ length: COUNT[sn - 1] }, (x, k) => {
        const st = stateOf(sn, k + 1), d = sn === 1 ? S1[k] : ['Episode ' + (k + 1), [], 0, 0];
        return { n: 'E' + (k + 1), title: d[0], href: st === 'done' ? 'Title.dc.html' : '#', len: '22 min', tags: d[1].map((t) => ({ name: t, style: chip(t, d[2] ? 'proposed' : 'accepted') })), review: d[3] ? d[3] + ' to review' : '', state: WORD[st], dot: 'flex:none;width:8px;height:8px;border-radius:50%;box-sizing:border-box;' + COL[st] };
      })
    };
  }
}
</script>


</body></html>