// lib/support.js
// Smart customer service — guided returns with photo-based defect detection.
//
// The shopper is walked through photographing the item; the client extracts
// image features (brightness, edge density, colour variance…) and this service
// classifies the likely defect, then drafts the return form, refund and pickup
// automatically.
//
// Production would run the photo through a vision model fine-tuned on defect
// classes; the session -> analyse -> return-form contract is unchanged.
import { getProduct, getProfile, seededRandom } from './store.js';

const DEFECTS = {
  stain: {
    label: 'Staining / soiling', label_zh: '污漬 / 髒污',
    cause: 'Shipping, storage or handling contamination.',
    cause_zh: '運送、倉儲或搬運過程造成的污染。',
    resolution_zh: '符合退貨條件，可全額退款或換貨。',
    resolution: 'Eligible for a full refund or replacement.',
  },
  tear: {
    label: 'Tear / stitching defect', label_zh: '破損 / 車線瑕疵',
    cause: 'Manufacturing or seam integrity defect.',
    cause_zh: '製造或縫線結構瑕疵。',
    resolution_zh: '屬商品瑕疵，優先安排換貨並全額退款運費。',
    resolution: 'Manufacturing defect — replacement prioritised, shipping refunded.',
  },
  colour: {
    label: 'Colour mismatch', label_zh: '色差 / 與圖片不符',
    cause: 'Product differs from the listing imagery.',
    cause_zh: '實品顏色與商品圖片不符。',
    resolution_zh: '屬描述不符，可全額退款。',
    resolution: 'Not as described — full refund applies.',
  },
  fade: {
    label: 'Fading / wear', label_zh: '褪色 / 使用痕跡',
    cause: 'Normal wear or washing.',
    cause_zh: '正常使用或洗滌造成的耗損。',
    resolution_zh: '需人工複核；若為首次洗滌造成可申請部分退款。',
    resolution: 'Manual review required; partial refund if caused by first wash.',
  },
  size: {
    label: 'Size / fit issue', label_zh: '尺寸不合',
    cause: 'Fit differs from expectation.',
    cause_zh: '實際版型與預期不同。',
    resolution_zh: '可免費換尺寸一次（依尺寸建議調整）。',
    resolution: 'One free size exchange (adjusted by our size advisor).',
  },
  none: {
    label: 'No defect detected', label_zh: '未偵測到明顯瑕疵',
    cause: 'Image appears clean.',
    cause_zh: '照片中未發現明顯瑕疵。',
    resolution_zh: '請補拍其他角度或改以「尺寸不合」申請。',
    resolution: 'Please retake from another angle, or file it as a size issue.',
  },
};

const sessions = [];
const returns = [];
let sessionSeq = 5000;
let rmaSeq = 7000;

export const RETURN_REASONS = [
  { id: 'defect', zh: '商品有瑕疵', en: 'Item is defective' },
  { id: 'size', zh: '尺寸不合', en: 'Wrong size / fit' },
  { id: 'not_as_described', zh: '與描述不符', en: 'Not as described' },
  { id: 'changed_mind', zh: '改變心意', en: 'Changed my mind' },
  { id: 'late', zh: '延遲到貨', en: 'Arrived late' },
];

export function startSession({ productId, reason = 'defect', orderId = null, lang = 'zh' }) {
  const product = getProduct(productId);
  if (!product) return null;
  const profile = getProfile();
  sessionSeq += 1;
  const session = {
    id: `S-${sessionSeq}`,
    productId,
    product: { id: product.id, name: product.name, name_zh: product.name_zh, emoji: product.emoji, color: product.color, price: product.price },
    reason,
    orderId: orderId || `ORD-${8800 + Math.floor(Math.random() * 100)}`,
    customer: { name: profile.user.name, avatar: profile.user.avatar },
    createdAt: new Date().toISOString(),
    steps: [
      { id: 'order', zh: '選擇訂單與商品', en: 'Select order and item', status: 'done' },
      { id: 'reason', zh: '說明退貨原因', en: 'Tell us what went wrong', status: 'done' },
      { id: 'photo', zh: '上傳瑕疵照片（AI 檢測）', en: 'Upload photos (AI inspection)', status: 'active' },
      { id: 'form', zh: '確認退貨單與收件時間', en: 'Confirm return form and pickup', status: 'pending' },
    ],
  };
  sessions.push(session);
  return session;
}

function getSession(id) {
  return sessions.find((s) => s.id === id) || null;
}

// Classify a defect from client-extracted image features.
export function analyzePhoto({ sessionId, features = {}, lang = 'zh' }) {
  const session = getSession(sessionId);
  const zh = lang !== 'en';
  const {
    brightness = 0.5,        // 0..1 mean luminance
    edgeDensity = 0.15,      // 0..1 share of strong gradient pixels
    colourVariance = 0.05,   // 0..1 spread of sampled colours
    darkSpotRatio = 0.02,    // 0..1 share of very dark pixels
    saturation = 0.4,        // 0..1 mean saturation
    samples = 1,
  } = features;

  // Each signal is an "excess over what a clean photo looks like", normalised to
  // roughly 0..1, so the classes are comparable and one baseline term cannot
  // dominate every photo.
  const c01 = (v) => Math.max(0, Math.min(1, v));

  const evidence = {
    // Dark blotches and an overall dim frame suggest soiling.
    stain: c01((darkSpotRatio - 0.06) / 0.22) * 1.0 + c01((0.75 - brightness) / 0.35) * 0.35,
    // Sharp high-frequency edges suggest a tear or a broken seam.
    tear: c01((edgeDensity - 0.14) / 0.28) * 1.0 + c01((colourVariance - 0.1) / 0.3) * 0.2,
    // Variegated, oversaturated colour suggests a mismatch with the listing.
    colour: c01((colourVariance - 0.09) / 0.28) * 0.9 + c01((saturation - 0.45) / 0.35) * 0.3,
    // Flat, desaturated, bright and uniform suggests fading.
    fade: c01((0.28 - saturation) / 0.25) * 0.75
      + c01((0.06 - colourVariance) / 0.06) * 0.7
      + c01((brightness - 0.65) / 0.3) * 0.3,
    // Clean = smooth, evenly lit, no dark spots.
    none: c01((0.16 - edgeDensity) / 0.16) * 0.5 + c01((0.06 - darkSpotRatio) / 0.06) * 0.6,
  };

  let best = 'none';
  let bestScore = -Infinity;
  for (const [k, v] of Object.entries(evidence)) {
    if (v > bestScore) { bestScore = v; best = k; }
  }

  const total = Object.values(evidence).reduce((a, b) => a + b, 0) || 1;
  const confidence = Math.max(0.41, Math.min(0.96, bestScore / total + 0.32));
  const defect = DEFECTS[best];

  const detected = best !== 'none';
  const result = {
    sessionId,
    defect: best,
    label: defect.label,
    label_zh: defect.label_zh,
    cause: defect.cause,
    cause_zh: defect.cause_zh,
    resolution: defect.resolution,
    resolution_zh: defect.resolution_zh,
    confidence: Math.round(confidence * 100) / 100,
    detected,
    features,
    evidence: Object.entries(evidence)
      .map(([k, v]) => ({ defect: k, score: Math.round((v / total) * 100) / 100 }))
      .sort((a, b) => b.score - a.score),
    guidance: detected
      ? (zh
          ? `AI 已辨識出「${defect.label_zh}」，判定為${defect.cause_zh}建議下一步：建立退貨單。`
          : `AI identified "${defect.label}" — ${defect.cause} Next step: generate the return form.`)
      : (zh
          ? '這張照片看不到明顯瑕疵，建議補拍接縫、標籤或污點特寫，或改以「尺寸不合」申請。'
          : 'No clear defect in this photo. Try a close-up of the seams, label or marks, or file it as a size issue.'),
  };

  if (session) {
    session.analysis = result;
    session.steps = session.steps.map((s) =>
      s.id === 'photo' ? { ...s, status: detected ? 'done' : 'active' } : s,
    );
  }
  return result;
}

export function submitReturn({ sessionId, defect = null, reason = null, note = '', lang = 'zh' }) {
  const session = getSession(sessionId);
  if (!session) return null;
  const zh = lang !== 'en';
  const product = getProduct(session.productId);
  const profile = getProfile();
  const rand = seededRandom(`rma-${session.id}`);
  rmaSeq += 1;

  const finalReason = reason || session.reason;
  const analysis = session.analysis;
  const defectKey = defect || analysis?.defect || (finalReason === 'size' ? 'size' : 'none');
  const d = DEFECTS[defectKey] || DEFECTS.none;

  const withinWindow = true; // demo: always inside the 14-day window
  const refundFull = d !== DEFECTS.fade;
  const refundAmount = Math.round(product.price * (refundFull ? 1 : 0.5) * 100) / 100;
  const shippingRefund = defectKey === 'tear' || defectKey === 'colour';

  const pickupDate = new Date(Date.now() + (1 + Math.floor(rand() * 2)) * 86400000);
  const window = rand() < 0.5 ? '09:00–12:00' : '14:00–18:00';

  const form = {
    rma: `RMA-${new Date().getFullYear()}-${rmaSeq}`,
    sessionId: session.id,
    orderId: session.orderId,
    product: session.product,
    customer: session.customer,
    reason: finalReason,
    reasonLabel: RETURN_REASONS.find((r) => r.id === finalReason)?.zh || finalReason,
    reasonLabel_en: RETURN_REASONS.find((r) => r.id === finalReason)?.en || finalReason,
    defect: { key: defectKey, label: d.label, label_zh: d.label_zh, confidence: analysis?.confidence ?? null },
    withinWindow,
    refund: {
      amount: refundAmount,
      currency: 'USD',
      method: zh ? '原信用卡' : 'Original card',
      shippingRefunded: shippingRefund,
      fullRefund: refundFull,
    },
    pickup: {
      date: pickupDate.toISOString(),
      window,
      carrier: zh ? '順豐到府收件' : 'SF Express home pickup',
      free: true,
    },
    note,
    estimatedRefundDays: refundFull ? 3 : 5,
    status: 'approved',
    createdAt: new Date().toISOString(),
    timeline: [
      { zh: '申請已送出', en: 'Request submitted', done: true },
      { zh: 'AI 瑕疵檢測完成', en: 'AI defect inspection complete', done: !!analysis },
      { zh: '退貨單已建立，等待收件', en: 'Return form created, awaiting pickup', done: true },
      { zh: `預計 ${refundFull ? 3 : 5} 個工作天內退款`, en: `Refund within ${refundFull ? 3 : 5} business days`, done: false },
    ],
  };

  returns.push(form);
  if (session) {
    session.steps = session.steps.map((s) => ({ ...s, status: 'done' }));
    session.returnForm = form;
  }

  const zh2 = zh;
  form.message = zh2
    ? `已完成！退貨單號 ${form.rma}，${window} 由${form.pickup.carrier}收件，退款 HK$${Math.round(refundAmount * 7.8).toLocaleString()} 將於 ${form.estimatedRefundDays} 個工作天內退回${form.refund.method}。`
    : `All set! Return ${form.rma} is approved. Pickup is scheduled for ${window} via ${form.pickup.carrier}, and US$${refundAmount.toFixed(2)} will be refunded to your ${form.refund.method} within ${form.estimatedRefundDays} business days.`;

  return form;
}

export function getReturns() {
  return returns;
}

export function getSessionById(id) {
  return getSession(id);
}

export function returnStats(lang = 'zh') {
  const zh = lang !== 'en';
  return {
    sessionsHandled: sessions.length,
    formsGenerated: returns.length,
    autoApproved: returns.filter((r) => r.status === 'approved').length,
    avgResolutionMinutes: 3.4,
    label: zh ? 'AI 客服平均處理時間' : 'Average AI handling time',
  };
}
