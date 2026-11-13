<script setup>
// A scene on a slide: `scene(scr, look, data, { step, tick, pick })` drawn on a pixelated canvas,
// again whenever the step (the slide's clicks) changes, every frame if `fps`, and on a click (the
// pixel clicked, `pick`, until the next click). With `grow` ({ at, from, to, ms }), the click that
// reaches step `at` grows the new picture's `to` rectangle out of the old one's `from` (a rectangle,
// or a function giving it), once, in `ms`: a transition the click starts, never a loop.
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { screen } from "./screen.js";
import { at, blit, loop } from "./blit.js";
import { LOOKS } from "./looks.js";

const props = defineProps({
  scene: { type: Function, required: true },
  data: { default: null },
  step: { type: Number, default: 0 },
  look: { type: String, default: "arcade" },
  w: { type: Number, default: 640 },
  h: { type: Number, default: 360 },
  fps: { type: Number, default: 0 },
  grow: { type: Object, default: null },
  height: { type: String, default: "400px" }, // the scene's box on the slide; the pixels fit inside it, square
});
const canvas = ref(null);
const scr = screen(props.w, props.h);
let tick = 0, ticks = 0, since = 0, pick = null, stop = null, frame = 0; // tick: frames since the step changed

function draw() {
  if (!canvas.value) return;
  const look = LOOKS[props.look];
  props.scene(scr, look, props.data, { step: props.step, tick, pick });
  blit(scr, canvas.value, look.palette);
}
function click(e) {
  pick = at(e, canvas.value);
  draw();
}
/** A copy of the canvas as it stands. */
function copy() {
  const c = document.createElement("canvas");
  (c.width = canvas.value.width), (c.height = canvas.value.height);
  c.getContext("2d").drawImage(canvas.value, 0, 0);
  return c;
}
/** The new picture, its `to` rectangle growing out of `from` over the old picture's. */
function grow(old, fresh, from, to, ms) {
  const ctx = canvas.value.getContext("2d"), t0 = performance.now();
  ctx.imageSmoothingEnabled = false;
  cancelAnimationFrame(frame);
  const paint = (t) => {
    const k = Math.min(1, (t - t0) / ms), e = 1 - (1 - k) ** 3; // eased out
    const r = from.map((v, i) => Math.round(v + (to[i] - v) * e));
    ctx.drawImage(fresh, 0, 0);
    ctx.drawImage(old, ...to, ...to);
    ctx.drawImage(fresh, ...to, ...r);
    if (k < 1) frame = requestAnimationFrame(paint);
  };
  frame = requestAnimationFrame(paint);
}
onMounted(() => {
  draw();
  if (props.fps) stop = loop((t) => ((ticks = t), (tick = t - since), draw()), props.fps);
});
onBeforeUnmount(() => (stop?.(), cancelAnimationFrame(frame)));
watch(
  () => [props.step, props.data, props.look],
  ([step], [before]) => {
    const g = props.grow, growing = g && canvas.value && step === g.at && before === g.at - 1;
    const old = growing ? copy() : null;
    if (step !== before) (since = ticks), (tick = 0);
    draw();
    if (growing) grow(old, copy(), typeof g.from === "function" ? g.from() : g.from, g.to, g.ms ?? 450);
  },
);
</script>

<template>
  <canvas ref="canvas" class="pixel" :style="{ height }" @click.stop="click" />
</template>

<style scoped>
.pixel {
  width: 100%;
  object-fit: contain;
  image-rendering: pixelated;
  display: block;
}
</style>
