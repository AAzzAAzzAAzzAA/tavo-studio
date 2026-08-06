tavo.plugin.onInputAction("insert-marker", async () => {
  await tavo.input.append(tavo.plugin.i18n.t("runtime.marker"));
});
