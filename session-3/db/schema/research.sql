CREATE TABLE sources (id INTEGER PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE notes (
  id INTEGER PRIMARY KEY, topic TEXT NOT NULL, content TEXT NOT NULL,
  source_id INTEGER REFERENCES sources(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE reports (
  id INTEGER PRIMARY KEY, topic TEXT NOT NULL, body TEXT NOT NULL,
  review_rounds INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- SQLite full-text search (FTS5). rowid = the row id in the table it indexes.
CREATE VIRTUAL TABLE sources_fts USING fts5(title, body);
CREATE VIRTUAL TABLE notes_fts USING fts5(topic, content);
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
  INSERT INTO notes_fts(rowid, topic, content) VALUES (new.id, new.topic, new.content);
END;
CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
  DELETE FROM notes_fts WHERE rowid = old.id;
END;
