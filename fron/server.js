const express = require("express");
const path = require("path");

const app = express();
const port = 5500;
const staticDir = path.join(__dirname);

app.use(express.static(staticDir));

app.get("/", (req, res) => {
  res.sendFile(path.join(staticDir, "index.html"));
});

app.listen(port, () => {
  console.log(`Frontend servido en http://127.0.0.1:${port}`);
});
