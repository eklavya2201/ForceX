(() => {
  const address = document.querySelector('#address');
  const form = document.querySelector('#address-form');
  const frame = document.querySelector('#page');
  const error = document.querySelector('#browser-error');
  const origin = window.location.origin;
  const senderSharePath = /^\/s\/[A-Za-z0-9_-]+\/?$/;
  let senderShareUrl = '';

  function forcexUrl(value) {
    const url = new URL(value, origin);
    if (url.origin !== origin || !['http:', 'https:'].includes(url.protocol)) {
      throw new Error('Only links from this ForceX server can be opened.');
    }
    return url.href;
  }

  function navigate(value, pasted = false) {
    try {
      const url = forcexUrl(value);
      const parsed = new URL(url);
      if (pasted && !senderSharePath.test(parsed.pathname)) {
        throw new Error('Paste the original sender link with an /s/ path. Internal /v/ links expire after use.');
      }
      if (pasted) senderShareUrl = url;
      error.hidden = true;
      address.value = senderShareUrl || url;
      frame.src = url;
    } catch (cause) {
      error.textContent = cause.message;
      error.hidden = false;
    }
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    navigate(address.value.trim(), true);
  });

  frame.addEventListener('load', () => {
    try {
      const loadedUrl = forcexUrl(frame.contentWindow.location.href);
      const parsed = new URL(loadedUrl);
      if (senderSharePath.test(parsed.pathname)) senderShareUrl = loadedUrl;
      address.value = senderShareUrl || loadedUrl;
    } catch {
      error.textContent = 'Only links from this ForceX server can be opened.';
      error.hidden = false;
    }
  });

  document.querySelector('#home').addEventListener('click', () => {
    senderShareUrl = '';
    navigate(origin);
  });
  document.querySelector('#back').addEventListener('click', () => frame.contentWindow.history.back());
  document.querySelector('#forward').addEventListener('click', () => frame.contentWindow.history.forward());
  document.querySelector('#reload').addEventListener('click', () => frame.contentWindow.location.reload());

  navigate(new URLSearchParams(window.location.search).get('url') || origin);
})();