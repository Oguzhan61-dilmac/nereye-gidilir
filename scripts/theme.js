(function () {
  const THEME_KEY = "nereyeGidilirTheme";
  const darkThemeValue = "dark";
  const lightThemeValue = "light";

  function getSavedTheme() {
    return localStorage.getItem(THEME_KEY);
  }

  function applyTheme(theme) {
    if (theme === darkThemeValue) {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.setAttribute("data-theme", "light");
    }
  }

  // Initialize theme
  const savedTheme = getSavedTheme();
  if (savedTheme) {
    applyTheme(savedTheme);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    applyTheme(darkThemeValue);
  } else {
    applyTheme(lightThemeValue);
  }

  window.toggleTheme = function () {
    const currentTheme = document.documentElement.getAttribute("data-theme");
    const newTheme = currentTheme === "dark" ? lightThemeValue : darkThemeValue;
    localStorage.setItem(THEME_KEY, newTheme);
    applyTheme(newTheme);
    updateThemeIcon(newTheme);
  };

  function updateThemeIcon(theme) {
    const iconEl = document.getElementById("themeIcon");
    if (iconEl) {
      iconEl.textContent = theme === "dark" ? "☀️" : "🌓";
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    updateThemeIcon(document.documentElement.getAttribute("data-theme") || lightThemeValue);
  });
})();
