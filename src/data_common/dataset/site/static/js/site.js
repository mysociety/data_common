document.querySelectorAll(".code-button").forEach(function (button) {
  button.addEventListener("click", function (event) {
    event.preventDefault();
    document.querySelector("#code-example")?.classList.remove("hidden");
    document.querySelector("#code-example")?.scrollIntoView({ behavior: "smooth" });
  });
});

document.querySelectorAll(".subscribe-button").forEach(function (button) {
  button.addEventListener("click", function (event) {
    event.preventDefault();
    document.querySelector("#subscribe")?.classList.remove("hidden");
    document.querySelector("#subscribe")?.scrollIntoView({ behavior: "smooth" });
  });
});

document.querySelectorAll(".download-link").forEach(function (button) {
  button.addEventListener("click", function () {
    window.setTimeout(function () {
      document.querySelector("#survey")?.scrollIntoView({ behavior: "smooth" });
    }, 400);
  });
});
