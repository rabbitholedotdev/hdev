-- {{titulo}}: o formato dos dados fica legível aqui (o agente da pessoa lê e grava direto).
-- Migração publicada não muda: mudança nova vira 002-....sql.

-- Quem já abriu o app (identidade da Ratoeira)
CREATE TABLE pessoas (
  email     TEXT PRIMARY KEY,
  nome      TEXT NOT NULL,
  papel     TEXT NOT NULL,
  visto_em  INTEGER NOT NULL      -- ms
);
