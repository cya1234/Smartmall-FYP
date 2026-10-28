// lib/social.js
// Private try-on voting — share a generated try-on look to a friends-only
// group and collect votes before buying.
//
// Privacy model: polls are scoped to one private group, expire automatically,
// are never publicly indexed, and the image is only visible to invited members.
// A production system would back this with per-group access control and signed,
// expiring media URLs; the poll/tally contract stays the same.
import { getProduct, getProfile, seededRandom } from './store.js';

export const GROUPS = [
  {
    id: 'bff', name: 'Close Friends', name_zh: '閨蜜團', emoji: '💬',
    members: [
      { id: 'f1', name: '阿欣', name_en: 'Yan', avatar: '👩', style: 'Fashion-forward' },
      { id: 'f2', name: '小美', name_en: 'Mei', avatar: '👧', style: 'Minimalist' },
      { id: 'f3', name: 'Carmen', name_en: 'Carmen', avatar: '👩‍🦰', style: 'Classic' },
      { id: 'f4', name: 'Suki', name_en: 'Suki', avatar: '👩‍🦱', style: 'Streetwear' },
      { id: 'f5', name: '阿豪', name_en: 'Ho', avatar: '🧑', style: 'Practical' },
    ],
  },
  {
    id: 'family', name: 'Family', name_zh: '家人群組', emoji: '🏠',
    members: [
      { id: 'm1', name: '媽媽', name_en: 'Mum', avatar: '👩‍🦳', style: 'Practical' },
      { id: 'm2', name: '姐姐', name_en: 'Sister', avatar: '👩‍🎓', style: 'Trendy' },
      { id: 'm3', name: '弟弟', name_en: 'Brother', avatar: '🧑‍🎤', style: 'Streetwear' },
    ],
  },
  {
    id: 'work', name: 'Colleagues', name_zh: '同事群組', emoji: '🏢',
    members: [
      { id: 'w1', name: 'Kevin', name_en: 'Kevin', avatar: '🧑‍💼', style: 'Formal' },
      { id: 'w2', name: 'Fiona', name_en: 'Fiona', avatar: '👩‍💼', style: 'Classic' },
      { id: 'w3', name: 'Ming', name_en: 'Ming', avatar: '🧑‍💻', style: 'Minimalist' },
    ],
  },
];

const VOTE_LABELS = {
  love: { zh: '超好看 🔥', en: 'Love it 🔥' },
  ok: { zh: '還不錯 👍', en: 'It works 👍' },
  no: { zh: '不太適合 🤔', en: 'Not for you 🤔' },
};

let seq = 2000;
const polls = [];

function tally(votes) {
  const t = { love: 0, ok: 0, no: 0, total: votes.length };
  for (const v of votes) if (t[v.vote] != null) t[v.vote] += 1;
  return t;
}

// Style affinity: does the friend's taste overlap the garment?
function affinity(friend, product) {
  const rand = seededRandom(`aff-${friend.id}-${product.id}`);
  let base = 0.62 + rand() * 0.28;
  const styles = (product.style || []).map((s) => s.toLowerCase());
  if (styles.includes(friend.style.toLowerCase())) base += 0.15;
  if (styles.includes('classic') && friend.style === 'Classic') base += 0.08;
  return Math.min(0.96, base);
}

function synthesizeVotes(poll, count) {
  const group = GROUPS.find((g) => g.id === poll.groupId) || GROUPS[0];
  const product = getProduct(poll.productId);
  const votes = [];
  for (let i = 0; i < Math.min(count, group.members.length); i++) {
    const member = group.members[i];
    const rand = seededRandom(`vote-${poll.id}-${member.id}`);
    const p = affinity(member, product);
    const r = rand();
    let vote;
    if (r < p * 0.85) vote = 'love';
    else if (r < p * 0.85 + 0.18) vote = 'ok';
    else vote = 'no';

    const reasons = {
      love: [
        { zh: '顏色很襯你的膚色，拍照一定好看', en: 'That colour suits you — great in photos' },
        { zh: '版型俐落，比你想像中更好搭', en: 'Clean cut, easier to style than you think' },
        { zh: '這個材質在這種場合很得體', en: 'The fabric reads really well for this occasion' },
      ],
      ok: [
        { zh: '不錯，但配件要挑一下', en: 'Nice, but pick the accessories carefully' },
        { zh: '可以，不過我覺得上一個顏色更好', en: 'Fine — though I preferred the other colour' },
        { zh: '安全牌，不會出錯', en: 'A safe choice, nothing will go wrong' },
      ],
      no: [
        { zh: '版型對你來說偏大，建議小一號', en: 'It runs big on you — try a size down' },
        { zh: '顏色跟你平常的風格不太搭', en: 'The colour is a bit off from your usual style' },
        { zh: '這個場合換一件會更適合', en: 'I would pick something else for this occasion' },
      ],
    }[vote];
    votes.push({
      voterId: member.id, name: member.name, name_en: member.name_en, avatar: member.avatar,
      vote, comment: reasons[Math.floor(rand() * reasons.length)], at: new Date(Date.now() - Math.floor(rand() * 3600000)).toISOString(),
    });
  }
  return votes;
}

function verdictFor(t) {
  if (t.total === 0) return { key: 'pending', zh: '等待朋友投票中', en: 'Waiting for votes', confidence: 0 };
  const lovePct = Math.round((t.love / t.total) * 100);
  const noPct = Math.round((t.no / t.total) * 100);
  if (lovePct >= 55) {
    return {
      key: 'go', zh: `朋友一致好評（${lovePct}% 超好看）`, en: `Friends love it (${lovePct}% love it)`,
      confidence: Math.min(0.95, 0.55 + lovePct / 200),
      advice_zh: '多數朋友認為這件很適合你，可以放心入手。',
      advice_en: 'Most of your friends think it suits you — go ahead with confidence.',
    };
  }
  if (noPct >= 40) {
    return {
      key: 'reconsider', zh: `朋友多數不建議（${noPct}% 不適合）`, en: `Friends lean no (${noPct}% not for you)`,
      confidence: Math.min(0.9, 0.5 + noPct / 200),
      advice_zh: '朋友認為版型或風格不太合適，建議先看其他款式或調整尺寸，可降低退貨機率。',
      advice_en: 'Your friends think the fit or style is off. Consider another option or size to reduce the chance of a return.',
    };
  }
  return {
    key: 'mixed', zh: '評價兩極，可再想想', en: 'Mixed feedback — worth a second look',
    confidence: 0.6,
    advice_zh: '朋友意見分歧，建議參考留言中提到的尺寸與搭配建議再決定。',
    advice_en: 'Opinions are split. Check the comments about sizing and styling before deciding.',
  };
}

export function createPoll({ productId, groupId = 'bff', note = '', imageAttached = false }) {
  const product = getProduct(productId);
  if (!product) return null;
  const profile = getProfile();
  seq += 1;
  const poll = {
    id: `V-${seq}`,
    productId,
    product: { id: product.id, name: product.name, name_zh: product.name_zh, emoji: product.emoji, color: product.color, price: product.price },
    groupId,
    note,
    imageAttached,
    createdBy: { name: profile.user.name, avatar: profile.user.avatar },
    createdAt: new Date().toISOString(),
    expiresInHours: 24,
    privacy: 'friends-only',
  };
  polls.unshift(poll);
  return decorate(poll);
}

function decorate(poll) {
  const group = GROUPS.find((g) => g.id === poll.groupId) || GROUPS[0];
  const votes = synthesizeVotes(poll, poll._voteCount ?? 0);
  const t = tally(votes);
  return {
    ...poll,
    group: { id: group.id, name: group.name, name_zh: group.name_zh, emoji: group.emoji, memberCount: group.members.length },
    members: group.members,
    votes,
    tally: t,
    verdict: verdictFor(t),
    voteLabels: VOTE_LABELS,
  };
}

export function getPolls() {
  return polls.map(decorate);
}

export function getPoll(id) {
  const p = polls.find((x) => x.id === id);
  return p ? decorate(p) : null;
}

// Friends respond over time — the demo equivalent of waiting for replies.
export function simulateVotes(id, count = null) {
  const poll = polls.find((x) => x.id === id);
  if (!poll) return null;
  const group = GROUPS.find((g) => g.id === poll.groupId) || GROUPS[0];
  const target = count == null ? group.members.length : Math.min(count, group.members.length);
  poll._voteCount = Math.max(poll._voteCount || 0, target);
  return decorate(poll);
}

export function castVote(id, { vote, comment = '', voterId = 'me' }) {
  const poll = polls.find((x) => x.id === id);
  if (!poll) return null;
  // In this demo the shopper can also record their own pick; friend votes come
  // from simulateVotes. Keep it simple: bump the simulated set to full.
  poll._voteCount = Math.max(poll._voteCount || 0, 1);
  const decorated = decorate(poll);
  decorated.selfVote = { vote, comment, voterId, at: new Date().toISOString() };
  return decorated;
}

export function socialImpact() {
  const all = getPolls();
  const decided = all.filter((p) => p.tally.total > 0);
  return {
    pollsCreated: all.length,
    votesCollected: all.reduce((s, p) => s + p.tally.total, 0),
    friendsInvolved: GROUPS.reduce((s, g) => s + g.members.length, 0),
    // Framing: social validation before purchase is linked to fewer returns.
    estimatedReturnReduction: decided.length ? Math.round(decided.length * 3.4 * 10) / 10 : 0,
  };
}
