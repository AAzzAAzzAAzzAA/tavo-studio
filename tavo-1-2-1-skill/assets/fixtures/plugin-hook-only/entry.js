tavo.plugin.on("chat:opened", async (event) => {
  console.log("Community hook-only chat marker", event.chatId);
});

tavo.plugin.on("input:beforeSend", async (event) => {
  event.text = event.text;
});
