-- Run this once in your Supabase project's SQL editor.
-- The Flask backend talks to these tables via the service-role key only —
-- never expose that key to the browser. Row Level Security is enabled with
-- no public policies, so the anon/public key (if you ever use one) gets no
-- access by default.

create extension if not exists "uuid-ossp";

create table if not exists couples (
  id uuid primary key default uuid_generate_v4(),
  code text unique not null,
  created_at timestamptz not null default now()
);

create table if not exists sessions (
  id uuid primary key default uuid_generate_v4(),
  couple_id uuid references couples(id) on delete set null,
  status text not null default 'awaiting_a'
    check (status in ('awaiting_a', 'awaiting_b', 'generating', 'swiping', 'round_complete',
                       'matched', 'final_choice', 'finalized')),
  round int not null default 1,
  matched_tmdb_id int,
  final_choice_tmdb_id int,
  brief_summary text default '',
  created_at timestamptz not null default now()
);

create table if not exists preferences (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid not null references sessions(id) on delete cascade,
  partner text not null check (partner in ('A', 'B')),
  mood text[] not null default '{}',
  mood_text text not null default '',
  languages text[] not null default '{}',
  content_type text not null,
  min_rating int not null,
  eras text[] not null default '{}',
  submitted_at timestamptz not null default now(),
  unique (session_id, partner)
);

create table if not exists titles (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid not null references sessions(id) on delete cascade,
  round int not null,
  tmdb_id int not null,
  media_type text not null check (media_type in ('movie', 'tv')),
  title text not null,
  year int,
  poster_url text,
  imdb_rating numeric,
  runtime int,
  synopsis text default '',
  ott_platforms jsonb not null default '[]',
  created_at timestamptz not null default now()
);
create index if not exists idx_titles_session_round on titles(session_id, round);

create table if not exists swipes (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid not null references sessions(id) on delete cascade,
  round int not null,
  partner text not null check (partner in ('A', 'B')),
  tmdb_id int not null,
  direction text not null check (direction in ('like', 'pass')),
  created_at timestamptz not null default now(),
  unique (session_id, round, partner, tmdb_id)
);
create index if not exists idx_swipes_session_round on swipes(session_id, round);

create table if not exists ratings (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid not null references sessions(id) on delete cascade,
  tmdb_id int not null,
  rating int not null check (rating between 1 and 5),
  note text default '',
  created_at timestamptz not null default now()
);

alter table couples enable row level security;
alter table sessions enable row level security;
alter table preferences enable row level security;
alter table titles enable row level security;
alter table swipes enable row level security;
alter table ratings enable row level security;
-- No policies are created, so only the service-role key (used server-side by
-- the Flask app) can read or write these tables.
