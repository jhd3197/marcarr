 data-dc-script="" data-props="{&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:820}}">
class Component extends DCLogic {
  renderVals() {
    const S = this.state || {};
    const step = S.step || 1;
    const libs = S.libs || { Movies: true, 'TV Shows': true };
    const ai = S.ai !== false;
    const scanning = !!S.scanning;
    const NAMES = ['Plex', 'Libraries', 'AI', 'Start'];
    const picked = Object.keys(libs).filter((k) => libs[k]);
    return {
      steps: NAMES.map((n, i) => ({ n: i + 1, name: n, cls: 'stp' + (i + 1 === step ? ' on' : i + 1 < step ? ' done' : '') })),
      is1: step === 1, is2: step === 2, is3: step === 3, is4: step === 4,
      tested: !!S.tested, test: () => this.setState({ tested: true }),
      libs: Object.keys(libs).map((k) => ({ name: k, on: libs[k], note: k === 'Movies' ? '8 films' : '1 show, 236 episodes', toggle: () => this.setState({ libs: { ...libs, [k]: !libs[k] } }) })),
      ai, noAi: !ai, aiYes: () => this.setState({ ai: true }), aiNo: () => this.setState({ ai: false }),
      lastTitle: scanning ? 'Scanning' : 'Ready',
      summary: [{ k: 'Plex', v: 'http://127.0.0.1:32400' }, { k: 'Libraries', v: picked.length ? picked.join(', ') : 'None picked' }, { k: 'AI', v: ai ? 'On, up to $10.00 a month' : 'Off' }],
      scanning, canBack: step > 1 && !scanning, back: () => this.setState({ step: step - 1 }),
      showNext: !scanning, nextLabel: step === 4 ? 'Start the first scan' : 'Next', next: () => this.setState(step === 4 ? { scanning: true } : { step: step + 1 })
    };
  }
}
</script>


</body></html>