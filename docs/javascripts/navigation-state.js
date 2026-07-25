(() => {
  const collapsibleSections = new Set([
    "/guide/",
    "/architecture/",
    "/reference/api/",
    "/development/",
  ]);
  const visibleOnlyWithinSections = new Set(["/reference/api/"]);
  const numberedSections = new Set(["/guide/"]);
  const desktopNavigation = window.matchMedia("(min-width: 76.25em)");
  const desktopToggleHandlers = new WeakMap();

  const withoutLocale = (pathname) =>
    pathname.replace(/^\/[a-z]{2}(?:-[a-z]{2,4})?\//i, "/");

  const normalizedPath = (value) => {
    const pathname = new URL(value, window.location.href).pathname;
    const localized = withoutLocale(pathname.replace(/index\.html$/, ""));
    return localized.endsWith("/") ? localized : `${localized}/`;
  };

  const markNavigationItem = (item, number, depth) => {
    for (const ellipsis of item.querySelectorAll(
      ":scope > a.md-nav__link > .md-ellipsis, " +
        ":scope > label.md-nav__link > .md-ellipsis",
    )) {
      let marker = ellipsis.querySelector(":scope > .pplx-nav-number");
      if (!marker) {
        marker = document.createElement("span");
        marker.className = "pplx-nav-number";
        marker.setAttribute("aria-hidden", "true");
        ellipsis.prepend(marker);
      }
      marker.textContent = `${number}${depth === 1 ? "." : ""} `;
    }
  };

  const numberNavigationList = (item, prefix = []) => {
    const list = item.querySelector(
      ":scope > nav.md-nav:not(.md-nav--secondary) > ul.md-nav__list",
    );
    if (!list) return;

    const children = Array.from(list.children).filter((child) =>
      child.matches("li.md-nav__item"),
    );
    children.forEach((child, index) => {
      const parts = [...prefix, index + 1];
      markNavigationItem(child, parts.join("."), parts.length);
      numberNavigationList(child, parts);
    });
  };

  const primaryNestedToggles = (item) =>
    Array.from(
      item.querySelectorAll("nav.md-nav input.md-nav__toggle"),
    ).filter(
      (nestedToggle) =>
        nestedToggle.closest("nav.md-nav--secondary") === null,
    );

  const removeDesktopToggleHandler = (label) => {
    if (!label) return;

    const handler = desktopToggleHandlers.get(label);
    if (!handler) return;

    label.removeEventListener("click", handler);
    desktopToggleHandlers.delete(label);
  };

  const updateNavigationState = () => {
    const currentPath = normalizedPath(window.location.href);
    const primary = document.querySelector("nav.md-nav--primary");
    if (!primary) return;

    for (const item of primary.querySelectorAll(
      ":scope > ul.md-nav__list > li.md-nav__item--section",
    )) {
      const link = item.querySelector(
        ":scope > .md-nav__container > a.md-nav__link[href]",
      );
      const toggle = item.querySelector(":scope > input.md-nav__toggle");
      if (!link || !toggle) continue;

      const sectionPath = normalizedPath(link.href);
      if (!collapsibleSections.has(sectionPath)) continue;

      const active = currentPath.startsWith(sectionPath);
      const hiddenOutsideSection =
        visibleOnlyWithinSections.has(sectionPath) && !active;
      item.classList.toggle("pplx-nav--section-hidden", hiddenOutsideSection);
      item.hidden = hiddenOutsideSection;
      if (numberedSections.has(sectionPath)) {
        numberNavigationList(item);
      } else {
        for (const marker of item.querySelectorAll(".pplx-nav-number")) {
          marker.remove();
        }
      }
      const children = item.querySelector(":scope > nav.md-nav");
      const label = item.querySelector(
        ":scope > .md-nav__container > label[for]",
      );

      if (!desktopNavigation.matches) {
        item.classList.remove("pplx-nav--path-aware", "pplx-nav--open");
        removeDesktopToggleHandler(label);
        toggle.classList.remove("md-toggle--indeterminate");
        toggle.indeterminate = false;
        toggle.checked = active;
        for (const nestedToggle of primaryNestedToggles(item)) {
          const nestedItem = nestedToggle.closest("li.md-nav__item");
          nestedToggle.indeterminate = false;
          nestedToggle.checked =
            nestedItem?.classList.contains("md-nav__item--active") ?? false;
        }
        children?.removeAttribute("aria-expanded");
        continue;
      }

      item.classList.add("pplx-nav--path-aware");
      toggle.classList.remove("md-toggle--indeterminate");
      toggle.indeterminate = false;
      const setExpanded = (expanded) => {
        item.classList.toggle("pplx-nav--open", expanded);
        toggle.checked = expanded;
        if (expanded) {
          for (const nestedToggle of primaryNestedToggles(item)) {
            nestedToggle.indeterminate = false;
            nestedToggle.checked = true;
          }
        }
        if (children) {
          children.setAttribute("aria-expanded", expanded ? "true" : "false");
        }
      };

      if (label && !desktopToggleHandlers.has(label)) {
        const handler = (event) => {
          event.preventDefault();
          event.stopPropagation();
          setExpanded(!item.classList.contains("pplx-nav--open"));
        };
        desktopToggleHandlers.set(label, handler);
        label.addEventListener("click", handler);
      }
      setExpanded(active);
    }
  };

  const schedule = () =>
    window.requestAnimationFrame(() =>
      window.requestAnimationFrame(updateNavigationState),
    );

  if (typeof window.document$?.subscribe === "function") {
    window.document$.subscribe(schedule);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule, { once: true });
  } else {
    schedule();
  }

  if (typeof desktopNavigation.addEventListener === "function") {
    desktopNavigation.addEventListener("change", schedule);
  } else {
    desktopNavigation.addListener(schedule);
  }
})();
