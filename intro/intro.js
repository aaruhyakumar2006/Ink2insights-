/* Ink 2 Insight – full-screen intro player.
   Usage:  Intro.play({ base: '/intro/', once: 'session' }).then(startApp);
   Always resolves (never blocks the app): on error, slow load, blocked autoplay or reduced motion it just skips. */
(function (g) {
  var LOAD_TIMEOUT_MS = 4000;
  function seen(mode) { try { return mode && sessionStorage.getItem('intro_seen') === '1'; } catch (e) { return false; } }
  function mark() { try { sessionStorage.setItem('intro_seen', '1'); } catch (e) {} }

  function play(opts) {
    opts = opts || {};
    var base = opts.base || 'intro/';
    return new Promise(function (resolve) {
      if (seen(opts.once) || new URLSearchParams(location.search).has('nointro') ||
          (g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches)) return resolve();

      var portrait = (g.matchMedia && g.matchMedia('(orientation: portrait)').matches) || (g.innerHeight >= g.innerWidth);
      var file = portrait ? 'intro-portrait.mp4' : 'intro-landscape.mp4';
      var poster = portrait ? 'poster-portrait.jpg' : 'poster-landscape.jpg';

      var root = document.createElement('div');
      root.className = 'intro'; root.setAttribute('role', 'dialog'); root.setAttribute('aria-label', 'Ink 2 Insight intro');
      root.innerHTML = '<video muted playsinline webkit-playsinline x5-playsinline preload="auto"></video>' +
        '<button class="skip" type="button">Skip</button>' +
        '<button class="snd" type="button" aria-pressed="false">Sound on</button>';
      var v = root.querySelector('video'), skip = root.querySelector('.skip'), snd = root.querySelector('.snd');
      v.poster = base + poster; v.src = base + file;
      document.body.appendChild(root);

      if (g.ReactNativeWebView && g.ReactNativeWebView.postMessage) {
        try { g.ReactNativeWebView.postMessage(JSON.stringify({ type: 'intro-start' })); } catch (e) {}
        try { g.ReactNativeWebView.postMessage(JSON.stringify({ type: 'intro:start' })); } catch (e) {}
      }

      var done = false, timer = setTimeout(finish, LOAD_TIMEOUT_MS);
      function finish() {
        if (done) return; done = true; clearTimeout(timer); mark();
        if (g.ReactNativeWebView && g.ReactNativeWebView.postMessage) {
          try { g.ReactNativeWebView.postMessage(JSON.stringify({ type: 'intro-end' })); } catch (e) {}
          try { g.ReactNativeWebView.postMessage(JSON.stringify({ type: 'intro:end' })); } catch (e) {}
        }
        root.classList.add('out');
        setTimeout(function () { root.remove(); resolve(); }, 600);
        v.pause();
      }
      skip.onclick = finish;
      v.onended = finish;
      v.onerror = finish;
      snd.onclick = function () {
        v.muted = !v.muted; snd.setAttribute('aria-pressed', String(!v.muted));
        snd.textContent = v.muted ? 'Sound on' : 'Sound off';
        if (v.paused) v.play().catch(function () {});
      };
      v.addEventListener('playing', function () { clearTimeout(timer); }, { once: true });
      var p = v.play();
      if (p && p.catch) p.catch(function () {            // autoplay blocked: show poster, tap to start, else give up
        clearTimeout(timer);
        var tap = document.createElement('button'); tap.className = 'tap'; tap.setAttribute('aria-label', 'Tap to play intro');
        tap.onclick = function () { tap.remove(); v.play().catch(finish); };
        root.appendChild(tap); timer = setTimeout(finish, 6000);
      });
    });
  }
  g.Intro = { play: play };
})(window);
