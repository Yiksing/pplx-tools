(() => {
  const storageKey = "pplx-tools-doc-locale";

  const alternateLinks = () =>
    Array.from(document.querySelectorAll('link[rel="alternate"][hreflang]'));

  const rememberSelection = (event) => {
    const link = event.target.closest("a[hreflang]");
    if (!link) return;
    const locale = link.getAttribute("hreflang");
    if (locale) window.localStorage.setItem(storageKey, locale);
  };

  const bestLocale = (supported) => {
    const saved = window.localStorage.getItem(storageKey);
    if (saved && supported.has(saved.toLowerCase())) return saved.toLowerCase();

    for (const requested of navigator.languages || [navigator.language]) {
      const normalized = requested.toLowerCase();
      if (supported.has(normalized)) return normalized;
      if (normalized === "zh-hk" || normalized === "zh-mo") {
        if (supported.has("zh-hant")) return "zh-hant";
      }
      if (normalized.startsWith("zh-")) {
        if (supported.has("zh-cn")) return "zh-cn";
      }
      const base = normalized.split("-")[0];
      if (supported.has(base)) return base;
    }
    return "en";
  };

  document.addEventListener("click", rememberSelection);

  const path = window.location.pathname.replace(/index\.html$/, "");
  if (path !== "/") return;
  if (window.localStorage.getItem(storageKey) === "en") return;

  const links = alternateLinks();
  const supported = new Map(
    links.map((link) => [
      link.getAttribute("hreflang").toLowerCase(),
      link.getAttribute("href"),
    ]),
  );
  const locale = bestLocale(supported);
  const destination = supported.get(locale);
  if (destination && locale !== "en") window.location.replace(destination);
})();
