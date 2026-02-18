use AiMind;

CREATE TABLE community_categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  slug VARCHAR(50) NOT NULL UNIQUE,
  label VARCHAR(100) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO community_categories (slug, label, sort_order) VALUES
  ('free', '자유게시판', 1),
  ('tips', '육아 꿀팁', 2),
  ('qna', 'Q&A', 3),
  ('review', '상담 후기', 4),
  ('expert', '전문가 칼럼', 5);

CREATE TABLE community_posts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  category_id INT NOT NULL,
  title VARCHAR(200) NOT NULL,
  content TEXT NOT NULL,
  view_count INT NOT NULL DEFAULT 0,
  like_count INT NOT NULL DEFAULT 0,
  comment_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_community_posts_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_community_posts_category FOREIGN KEY (category_id) REFERENCES community_categories(id),
  INDEX idx_community_posts_category (category_id),
  INDEX idx_community_posts_created (created_at)
);

CREATE TABLE community_post_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  post_id INT NOT NULL,
  image_url VARCHAR(1000) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_community_post_images_post FOREIGN KEY (post_id) REFERENCES community_posts(id),
  INDEX idx_community_post_images_post (post_id)
);

CREATE TABLE community_tags (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE community_post_tags (
  post_id INT NOT NULL,
  tag_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (post_id, tag_id),
  CONSTRAINT fk_community_post_tags_post FOREIGN KEY (post_id) REFERENCES community_posts(id),
  CONSTRAINT fk_community_post_tags_tag FOREIGN KEY (tag_id) REFERENCES community_tags(id)
);

CREATE TABLE community_comments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  post_id INT NOT NULL,
  user_id INT NOT NULL,
  parent_id INT NULL,
  content TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_community_comments_post FOREIGN KEY (post_id) REFERENCES community_posts(id),
  CONSTRAINT fk_community_comments_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_community_comments_parent FOREIGN KEY (parent_id) REFERENCES community_comments(id),
  INDEX idx_community_comments_post (post_id),
  INDEX idx_community_comments_created (created_at)
);

CREATE TABLE community_post_likes (
  post_id INT NOT NULL,
  user_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (post_id, user_id),
  CONSTRAINT fk_community_post_likes_post FOREIGN KEY (post_id) REFERENCES community_posts(id),
  CONSTRAINT fk_community_post_likes_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE community_post_bookmarks (
  post_id INT NOT NULL,
  user_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (post_id, user_id),
  CONSTRAINT fk_community_post_bookmarks_post FOREIGN KEY (post_id) REFERENCES community_posts(id),
  CONSTRAINT fk_community_post_bookmarks_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE expert_profiles (
  user_id INT PRIMARY KEY,
  title VARCHAR(100) NOT NULL,
  answer_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_expert_profiles_user FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Dummy data (execute after users.sql)
INSERT INTO users (
  email,
  password,
  name,
  profile_image_url,
  agree_terms,
  agree_privacy,
  agree_marketing
)
VALUES
  ('mom1@example.com', 'dummy', '걱정맘', 'https://example.com/images/users/mom1.jpg', 1, 1, 0),
  ('mom2@example.com', 'dummy', '행복한엄마', 'https://example.com/images/users/mom2.jpg', 1, 1, 1),
  ('mom3@example.com', 'dummy', '초보맘22', 'https://example.com/images/users/mom3.jpg', 1, 1, 0),
  ('expert1@example.com', 'dummy', '김미영', 'https://example.com/images/users/expert1.jpg', 1, 1, 0)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  agree_terms = VALUES(agree_terms),
  agree_privacy = VALUES(agree_privacy),
  agree_marketing = VALUES(agree_marketing);

INSERT INTO community_posts (
  user_id,
  category_id,
  title,
  content,
  view_count,
  like_count,
  comment_count,
  created_at,
  updated_at
)
SELECT
  (SELECT id FROM users WHERE email = 'mom1@example.com'),
  (SELECT id FROM community_categories WHERE slug = 'qna'),
  '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?',
  '아이가 최근에 그린 그림을 분석해보니 불안 징후가 나온다고 해서 걱정이 됩니다. 비슷한 경험 있으신 분 계신가요?',
  234,
  2,
  2,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
WHERE NOT EXISTS (
  SELECT 1 FROM community_posts
  WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'
);

INSERT INTO community_posts (
  user_id,
  category_id,
  title,
  content,
  view_count,
  like_count,
  comment_count,
  created_at,
  updated_at
)
SELECT
  (SELECT id FROM users WHERE email = 'expert1@example.com'),
  (SELECT id FROM community_categories WHERE slug = 'expert'),
  '[전문가 칼럼] 아이의 그림으로 읽는 마음 - 색상이 말하는 것들',
  '아이들이 사용하는 색상에는 특별한 의미가 담겨 있습니다. 오늘은 색상별로 아이의 심리 상태를 파악하는 방법을 알려드릴게요.',
  1523,
  1,
  0,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
WHERE NOT EXISTS (
  SELECT 1 FROM community_posts
  WHERE title = '[전문가 칼럼] 아이의 그림으로 읽는 마음 - 색상이 말하는 것들'
);

INSERT INTO community_posts (
  user_id,
  category_id,
  title,
  content,
  view_count,
  like_count,
  comment_count,
  created_at,
  updated_at
)
SELECT
  (SELECT id FROM users WHERE email = 'mom2@example.com'),
  (SELECT id FROM community_categories WHERE slug = 'review'),
  '상담센터 다녀왔어요! 마음숲 아동심리상담센터 솔직 후기',
  '지난주에 아이랑 같이 상담받고 왔는데요, 생각보다 너무 좋았어서 후기 남겨봅니다.',
  567,
  0,
  0,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
WHERE NOT EXISTS (
  SELECT 1 FROM community_posts
  WHERE title = '상담센터 다녀왔어요! 마음숲 아동심리상담센터 솔직 후기'
);

INSERT INTO community_post_images (post_id, image_url, sort_order)
SELECT post.id, 'https://example.com/images/post-1-1.jpg', 0
FROM community_posts post
WHERE post.title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'
  AND NOT EXISTS (
    SELECT 1 FROM community_post_images img
    WHERE img.post_id = post.id AND img.image_url = 'https://example.com/images/post-1-1.jpg'
  );

INSERT INTO community_post_images (post_id, image_url, sort_order)
SELECT post.id, 'https://example.com/images/post-1-2.jpg', 1
FROM community_posts post
WHERE post.title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'
  AND NOT EXISTS (
    SELECT 1 FROM community_post_images img
    WHERE img.post_id = post.id AND img.image_url = 'https://example.com/images/post-1-2.jpg'
  );

INSERT INTO community_post_images (post_id, image_url, sort_order)
SELECT post.id, 'https://example.com/images/post-2-1.jpg', 0
FROM community_posts post
WHERE post.title = '[전문가 칼럼] 아이의 그림으로 읽는 마음 - 색상이 말하는 것들'
  AND NOT EXISTS (
    SELECT 1 FROM community_post_images img
    WHERE img.post_id = post.id AND img.image_url = 'https://example.com/images/post-2-1.jpg'
  );

INSERT IGNORE INTO community_tags (name)
VALUES
  ('불안'),
  ('5세'),
  ('그림분석'),
  ('색상심리'),
  ('전문가칼럼'),
  ('상담후기');

INSERT IGNORE INTO community_post_tags (post_id, tag_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM community_tags WHERE name = '불안');

INSERT IGNORE INTO community_post_tags (post_id, tag_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM community_tags WHERE name = '5세');

INSERT IGNORE INTO community_post_tags (post_id, tag_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM community_tags WHERE name = '그림분석');

INSERT IGNORE INTO community_post_tags (post_id, tag_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '[전문가 칼럼] 아이의 그림으로 읽는 마음 - 색상이 말하는 것들'),
  (SELECT id FROM community_tags WHERE name = '색상심리');

INSERT IGNORE INTO community_post_tags (post_id, tag_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '[전문가 칼럼] 아이의 그림으로 읽는 마음 - 색상이 말하는 것들'),
  (SELECT id FROM community_tags WHERE name = '전문가칼럼');

INSERT IGNORE INTO community_post_tags (post_id, tag_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '상담센터 다녀왔어요! 마음숲 아동심리상담센터 솔직 후기'),
  (SELECT id FROM community_tags WHERE name = '상담후기');

INSERT INTO community_comments (post_id, user_id, parent_id, content)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM users WHERE email = 'mom2@example.com'),
  NULL,
  '저희도 비슷한 경험이 있었어요. 상담 받아보시는 걸 추천드려요.'
WHERE NOT EXISTS (
  SELECT 1 FROM community_comments
  WHERE content = '저희도 비슷한 경험이 있었어요. 상담 받아보시는 걸 추천드려요.'
);

INSERT INTO community_comments (post_id, user_id, parent_id, content)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM users WHERE email = 'expert1@example.com'),
  (SELECT id FROM community_comments WHERE content = '저희도 비슷한 경험이 있었어요. 상담 받아보시는 걸 추천드려요.'),
  '아이 그림은 맥락이 중요합니다. 최근 환경 변화가 있었는지 확인해보세요.'
WHERE NOT EXISTS (
  SELECT 1 FROM community_comments
  WHERE content = '아이 그림은 맥락이 중요합니다. 최근 환경 변화가 있었는지 확인해보세요.'
);

INSERT IGNORE INTO community_post_likes (post_id, user_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM users WHERE email = 'mom2@example.com');

INSERT IGNORE INTO community_post_likes (post_id, user_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM users WHERE email = 'mom3@example.com');

INSERT IGNORE INTO community_post_likes (post_id, user_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '[전문가 칼럼] 아이의 그림으로 읽는 마음 - 색상이 말하는 것들'),
  (SELECT id FROM users WHERE email = 'mom1@example.com');

INSERT IGNORE INTO community_post_bookmarks (post_id, user_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '5살 아이 그림에서 불안 징후가 보인다고 하는데, 어떻게 해야 할까요?'),
  (SELECT id FROM users WHERE email = 'mom3@example.com');

INSERT IGNORE INTO community_post_bookmarks (post_id, user_id)
SELECT
  (SELECT id FROM community_posts WHERE title = '[전문가 칼럼] 아이의 그림으로 읽는 마음 - 색상이 말하는 것들'),
  (SELECT id FROM users WHERE email = 'mom2@example.com');

INSERT INTO expert_profiles (user_id, title, answer_count)
VALUES
  ((SELECT id FROM users WHERE email = 'expert1@example.com'), '아동심리상담사', 234)
ON DUPLICATE KEY UPDATE
  title = VALUES(title),
  answer_count = VALUES(answer_count);

-- Quick checks
SELECT * FROM community_categories;
SELECT * FROM community_posts;
SELECT * FROM community_post_images;
SELECT * FROM community_tags;
SELECT * FROM community_post_tags;
SELECT * FROM community_comments;
SELECT * FROM community_post_likes;
SELECT * FROM community_post_bookmarks;
SELECT * FROM expert_profiles;
