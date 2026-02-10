/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./node_modules/colorthief/dist/color-thief.mjs":
/*!******************************************************!*\
  !*** ./node_modules/colorthief/dist/color-thief.mjs ***!
  \******************************************************/
/***/ ((__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) => {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (/* binding */ o)
/* harmony export */ });
if(!t)var t={map:function(t,r){var n={};return r?t.map(function(t,o){return n.index=o,r.call(n,t)}):t.slice()},naturalOrder:function(t,r){return t<r?-1:t>r?1:0},sum:function(t,r){var n={};return t.reduce(r?function(t,o,e){return n.index=e,t+r.call(n,o)}:function(t,r){return t+r},0)},max:function(r,n){return Math.max.apply(null,n?t.map(r,n):r)}};var r=function(){var r=5,n=8-r,o=1e3;function e(t,n,o){return(t<<2*r)+(n<<r)+o}function u(t){var r=[],n=!1;function o(){r.sort(t),n=!0}return{push:function(t){r.push(t),n=!1},peek:function(t){return n||o(),void 0===t&&(t=r.length-1),r[t]},pop:function(){return n||o(),r.pop()},size:function(){return r.length},map:function(t){return r.map(t)},debug:function(){return n||o(),r}}}function a(t,r,n,o,e,u,a){var i=this;i.r1=t,i.r2=r,i.g1=n,i.g2=o,i.b1=e,i.b2=u,i.histo=a}function i(){this.vboxes=new u(function(r,n){return t.naturalOrder(r.vbox.count()*r.vbox.volume(),n.vbox.count()*n.vbox.volume())})}function c(r,n){if(n.count()){var o=n.r2-n.r1+1,u=n.g2-n.g1+1,a=t.max([o,u,n.b2-n.b1+1]);if(1==n.count())return[n.copy()];var i,c,f,s,h=0,v=[],l=[];if(a==o)for(i=n.r1;i<=n.r2;i++){for(s=0,c=n.g1;c<=n.g2;c++)for(f=n.b1;f<=n.b2;f++)s+=r[e(i,c,f)]||0;v[i]=h+=s}else if(a==u)for(i=n.g1;i<=n.g2;i++){for(s=0,c=n.r1;c<=n.r2;c++)for(f=n.b1;f<=n.b2;f++)s+=r[e(c,i,f)]||0;v[i]=h+=s}else for(i=n.b1;i<=n.b2;i++){for(s=0,c=n.r1;c<=n.r2;c++)for(f=n.g1;f<=n.g2;f++)s+=r[e(c,f,i)]||0;v[i]=h+=s}return v.forEach(function(t,r){l[r]=h-t}),function(t){var r,o,e,u,a,c=t+"1",f=t+"2",s=0;for(i=n[c];i<=n[f];i++)if(v[i]>h/2){for(e=n.copy(),u=n.copy(),a=(r=i-n[c])<=(o=n[f]-i)?Math.min(n[f]-1,~~(i+o/2)):Math.max(n[c],~~(i-1-r/2));!v[a];)a++;for(s=l[a];!s&&v[a-1];)s=l[--a];return e[f]=a,u[c]=e[f]+1,[e,u]}}(a==o?"r":a==u?"g":"b")}}return a.prototype={volume:function(t){var r=this;return r._volume&&!t||(r._volume=(r.r2-r.r1+1)*(r.g2-r.g1+1)*(r.b2-r.b1+1)),r._volume},count:function(t){var r=this,n=r.histo;if(!r._count_set||t){var o,u,a,i=0;for(o=r.r1;o<=r.r2;o++)for(u=r.g1;u<=r.g2;u++)for(a=r.b1;a<=r.b2;a++)i+=n[e(o,u,a)]||0;r._count=i,r._count_set=!0}return r._count},copy:function(){var t=this;return new a(t.r1,t.r2,t.g1,t.g2,t.b1,t.b2,t.histo)},avg:function(t){var n=this,o=n.histo;if(!n._avg||t){var u,a,i,c,f=0,s=1<<8-r,h=0,v=0,l=0;for(a=n.r1;a<=n.r2;a++)for(i=n.g1;i<=n.g2;i++)for(c=n.b1;c<=n.b2;c++)f+=u=o[e(a,i,c)]||0,h+=u*(a+.5)*s,v+=u*(i+.5)*s,l+=u*(c+.5)*s;n._avg=f?[~~(h/f),~~(v/f),~~(l/f)]:[~~(s*(n.r1+n.r2+1)/2),~~(s*(n.g1+n.g2+1)/2),~~(s*(n.b1+n.b2+1)/2)]}return n._avg},contains:function(t){var r=this,o=t[0]>>n;return gval=t[1]>>n,bval=t[2]>>n,o>=r.r1&&o<=r.r2&&gval>=r.g1&&gval<=r.g2&&bval>=r.b1&&bval<=r.b2}},i.prototype={push:function(t){this.vboxes.push({vbox:t,color:t.avg()})},palette:function(){return this.vboxes.map(function(t){return t.color})},size:function(){return this.vboxes.size()},map:function(t){for(var r=this.vboxes,n=0;n<r.size();n++)if(r.peek(n).vbox.contains(t))return r.peek(n).color;return this.nearest(t)},nearest:function(t){for(var r,n,o,e=this.vboxes,u=0;u<e.size();u++)((n=Math.sqrt(Math.pow(t[0]-e.peek(u).color[0],2)+Math.pow(t[1]-e.peek(u).color[1],2)+Math.pow(t[2]-e.peek(u).color[2],2)))<r||void 0===r)&&(r=n,o=e.peek(u).color);return o},forcebw:function(){var r=this.vboxes;r.sort(function(r,n){return t.naturalOrder(t.sum(r.color),t.sum(n.color))});var n=r[0].color;n[0]<5&&n[1]<5&&n[2]<5&&(r[0].color=[0,0,0]);var o=r.length-1,e=r[o].color;e[0]>251&&e[1]>251&&e[2]>251&&(r[o].color=[255,255,255])}},{quantize:function(f,s){if(!f.length||s<2||s>256)return!1;var h=function(t){var o,u=new Array(1<<3*r);return t.forEach(function(t){o=e(t[0]>>n,t[1]>>n,t[2]>>n),u[o]=(u[o]||0)+1}),u}(f);h.forEach(function(){});var v=function(t,r){var o,e,u,i=1e6,c=0,f=1e6,s=0,h=1e6,v=0;return t.forEach(function(t){(o=t[0]>>n)<i?i=o:o>c&&(c=o),(e=t[1]>>n)<f?f=e:e>s&&(s=e),(u=t[2]>>n)<h?h=u:u>v&&(v=u)}),new a(i,c,f,s,h,v,r)}(f,h),l=new u(function(r,n){return t.naturalOrder(r.count(),n.count())});function g(t,r){for(var n,e=t.size(),u=0;u<o;){if(e>=r)return;if(u++>o)return;if((n=t.pop()).count()){var a=c(h,n),i=a[0],f=a[1];if(!i)return;t.push(i),f&&(t.push(f),e++)}else t.push(n),u++}}l.push(v),g(l,.75*s);for(var p=new u(function(r,n){return t.naturalOrder(r.count()*r.volume(),n.count()*n.volume())});l.size();)p.push(l.pop());g(p,s);for(var b=new i;p.size();)b.push(p.pop());return b}}}().quantize,n=function(t){this.canvas=document.createElement("canvas"),this.context=this.canvas.getContext("2d"),this.width=this.canvas.width=t.naturalWidth,this.height=this.canvas.height=t.naturalHeight,this.context.drawImage(t,0,0,this.width,this.height)};n.prototype.getImageData=function(){return this.context.getImageData(0,0,this.width,this.height)};var o=function(){};o.prototype.getColor=function(t,r){return void 0===r&&(r=10),this.getPalette(t,5,r)[0]},o.prototype.getPalette=function(t,o,e){var u=function(t){var r=t.colorCount,n=t.quality;if(void 0!==r&&Number.isInteger(r)){if(1===r)throw new Error("colorCount should be between 2 and 20. To get one color, call getColor() instead of getPalette()");r=Math.max(r,2),r=Math.min(r,20)}else r=10;return(void 0===n||!Number.isInteger(n)||n<1)&&(n=10),{colorCount:r,quality:n}}({colorCount:o,quality:e}),a=new n(t),i=function(t,r,n){for(var o,e,u,a,i,c=t,f=[],s=0;s<r;s+=n)e=c[0+(o=4*s)],u=c[o+1],a=c[o+2],(void 0===(i=c[o+3])||i>=125)&&(e>250&&u>250&&a>250||f.push([e,u,a]));return f}(a.getImageData().data,a.width*a.height,u.quality),c=r(i,u.colorCount);return c?c.palette():null},o.prototype.getColorFromUrl=function(t,r,n){var o=this,e=document.createElement("img");e.addEventListener("load",function(){var u=o.getPalette(e,5,n);r(u[0],t)}),e.src=t},o.prototype.getImageData=function(t,r){var n=new XMLHttpRequest;n.open("GET",t,!0),n.responseType="arraybuffer",n.onload=function(){if(200==this.status){var t=new Uint8Array(this.response);i=t.length;for(var n=new Array(i),o=0;o<t.length;o++)n[o]=String.fromCharCode(t[o]);var e=n.join(""),u=window.btoa(e);r("data:image/png;base64,"+u)}},n.send()},o.prototype.getColorAsync=function(t,r,n){var o=this;this.getImageData(t,function(t){var e=document.createElement("img");e.addEventListener("load",function(){var t=o.getPalette(e,5,n);r(t[0],this)}),e.src=t})};


/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/define property getters */
/******/ 	(() => {
/******/ 		// define getter functions for harmony exports
/******/ 		__webpack_require__.d = (exports, definition) => {
/******/ 			for(var key in definition) {
/******/ 				if(__webpack_require__.o(definition, key) && !__webpack_require__.o(exports, key)) {
/******/ 					Object.defineProperty(exports, key, { enumerable: true, get: definition[key] });
/******/ 				}
/******/ 			}
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/hasOwnProperty shorthand */
/******/ 	(() => {
/******/ 		__webpack_require__.o = (obj, prop) => (Object.prototype.hasOwnProperty.call(obj, prop))
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/make namespace object */
/******/ 	(() => {
/******/ 		// define __esModule on exports
/******/ 		__webpack_require__.r = (exports) => {
/******/ 			if(typeof Symbol !== 'undefined' && Symbol.toStringTag) {
/******/ 				Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 			}
/******/ 			Object.defineProperty(exports, '__esModule', { value: true });
/******/ 		};
/******/ 	})();
/******/ 	
/************************************************************************/
var __webpack_exports__ = {};
// This entry need to be wrapped in an IIFE because it need to be isolated against other modules in the chunk.
(() => {
/*!**************************************!*\
  !*** ./resources/js/extractColor.js ***!
  \**************************************/
__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var _node_modules_colorthief_dist_color_thief_mjs__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ../../node_modules/colorthief/dist/color-thief.mjs */ "./node_modules/colorthief/dist/color-thief.mjs");


function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
function _regeneratorRuntime() { "use strict"; /*! regenerator-runtime -- Copyright (c) 2014-present, Facebook, Inc. -- license (MIT): https://github.com/facebook/regenerator/blob/main/LICENSE */ _regeneratorRuntime = function _regeneratorRuntime() { return exports; }; var exports = {}, Op = Object.prototype, hasOwn = Op.hasOwnProperty, defineProperty = Object.defineProperty || function (obj, key, desc) { obj[key] = desc.value; }, $Symbol = "function" == typeof Symbol ? Symbol : {}, iteratorSymbol = $Symbol.iterator || "@@iterator", asyncIteratorSymbol = $Symbol.asyncIterator || "@@asyncIterator", toStringTagSymbol = $Symbol.toStringTag || "@@toStringTag"; function define(obj, key, value) { return Object.defineProperty(obj, key, { value: value, enumerable: !0, configurable: !0, writable: !0 }), obj[key]; } try { define({}, ""); } catch (err) { define = function define(obj, key, value) { return obj[key] = value; }; } function wrap(innerFn, outerFn, self, tryLocsList) { var protoGenerator = outerFn && outerFn.prototype instanceof Generator ? outerFn : Generator, generator = Object.create(protoGenerator.prototype), context = new Context(tryLocsList || []); return defineProperty(generator, "_invoke", { value: makeInvokeMethod(innerFn, self, context) }), generator; } function tryCatch(fn, obj, arg) { try { return { type: "normal", arg: fn.call(obj, arg) }; } catch (err) { return { type: "throw", arg: err }; } } exports.wrap = wrap; var ContinueSentinel = {}; function Generator() {} function GeneratorFunction() {} function GeneratorFunctionPrototype() {} var IteratorPrototype = {}; define(IteratorPrototype, iteratorSymbol, function () { return this; }); var getProto = Object.getPrototypeOf, NativeIteratorPrototype = getProto && getProto(getProto(values([]))); NativeIteratorPrototype && NativeIteratorPrototype !== Op && hasOwn.call(NativeIteratorPrototype, iteratorSymbol) && (IteratorPrototype = NativeIteratorPrototype); var Gp = GeneratorFunctionPrototype.prototype = Generator.prototype = Object.create(IteratorPrototype); function defineIteratorMethods(prototype) { ["next", "throw", "return"].forEach(function (method) { define(prototype, method, function (arg) { return this._invoke(method, arg); }); }); } function AsyncIterator(generator, PromiseImpl) { function invoke(method, arg, resolve, reject) { var record = tryCatch(generator[method], generator, arg); if ("throw" !== record.type) { var result = record.arg, value = result.value; return value && "object" == _typeof(value) && hasOwn.call(value, "__await") ? PromiseImpl.resolve(value.__await).then(function (value) { invoke("next", value, resolve, reject); }, function (err) { invoke("throw", err, resolve, reject); }) : PromiseImpl.resolve(value).then(function (unwrapped) { result.value = unwrapped, resolve(result); }, function (error) { return invoke("throw", error, resolve, reject); }); } reject(record.arg); } var previousPromise; defineProperty(this, "_invoke", { value: function value(method, arg) { function callInvokeWithMethodAndArg() { return new PromiseImpl(function (resolve, reject) { invoke(method, arg, resolve, reject); }); } return previousPromise = previousPromise ? previousPromise.then(callInvokeWithMethodAndArg, callInvokeWithMethodAndArg) : callInvokeWithMethodAndArg(); } }); } function makeInvokeMethod(innerFn, self, context) { var state = "suspendedStart"; return function (method, arg) { if ("executing" === state) throw new Error("Generator is already running"); if ("completed" === state) { if ("throw" === method) throw arg; return doneResult(); } for (context.method = method, context.arg = arg;;) { var delegate = context.delegate; if (delegate) { var delegateResult = maybeInvokeDelegate(delegate, context); if (delegateResult) { if (delegateResult === ContinueSentinel) continue; return delegateResult; } } if ("next" === context.method) context.sent = context._sent = context.arg;else if ("throw" === context.method) { if ("suspendedStart" === state) throw state = "completed", context.arg; context.dispatchException(context.arg); } else "return" === context.method && context.abrupt("return", context.arg); state = "executing"; var record = tryCatch(innerFn, self, context); if ("normal" === record.type) { if (state = context.done ? "completed" : "suspendedYield", record.arg === ContinueSentinel) continue; return { value: record.arg, done: context.done }; } "throw" === record.type && (state = "completed", context.method = "throw", context.arg = record.arg); } }; } function maybeInvokeDelegate(delegate, context) { var methodName = context.method, method = delegate.iterator[methodName]; if (undefined === method) return context.delegate = null, "throw" === methodName && delegate.iterator["return"] && (context.method = "return", context.arg = undefined, maybeInvokeDelegate(delegate, context), "throw" === context.method) || "return" !== methodName && (context.method = "throw", context.arg = new TypeError("The iterator does not provide a '" + methodName + "' method")), ContinueSentinel; var record = tryCatch(method, delegate.iterator, context.arg); if ("throw" === record.type) return context.method = "throw", context.arg = record.arg, context.delegate = null, ContinueSentinel; var info = record.arg; return info ? info.done ? (context[delegate.resultName] = info.value, context.next = delegate.nextLoc, "return" !== context.method && (context.method = "next", context.arg = undefined), context.delegate = null, ContinueSentinel) : info : (context.method = "throw", context.arg = new TypeError("iterator result is not an object"), context.delegate = null, ContinueSentinel); } function pushTryEntry(locs) { var entry = { tryLoc: locs[0] }; 1 in locs && (entry.catchLoc = locs[1]), 2 in locs && (entry.finallyLoc = locs[2], entry.afterLoc = locs[3]), this.tryEntries.push(entry); } function resetTryEntry(entry) { var record = entry.completion || {}; record.type = "normal", delete record.arg, entry.completion = record; } function Context(tryLocsList) { this.tryEntries = [{ tryLoc: "root" }], tryLocsList.forEach(pushTryEntry, this), this.reset(!0); } function values(iterable) { if (iterable) { var iteratorMethod = iterable[iteratorSymbol]; if (iteratorMethod) return iteratorMethod.call(iterable); if ("function" == typeof iterable.next) return iterable; if (!isNaN(iterable.length)) { var i = -1, next = function next() { for (; ++i < iterable.length;) if (hasOwn.call(iterable, i)) return next.value = iterable[i], next.done = !1, next; return next.value = undefined, next.done = !0, next; }; return next.next = next; } } return { next: doneResult }; } function doneResult() { return { value: undefined, done: !0 }; } return GeneratorFunction.prototype = GeneratorFunctionPrototype, defineProperty(Gp, "constructor", { value: GeneratorFunctionPrototype, configurable: !0 }), defineProperty(GeneratorFunctionPrototype, "constructor", { value: GeneratorFunction, configurable: !0 }), GeneratorFunction.displayName = define(GeneratorFunctionPrototype, toStringTagSymbol, "GeneratorFunction"), exports.isGeneratorFunction = function (genFun) { var ctor = "function" == typeof genFun && genFun.constructor; return !!ctor && (ctor === GeneratorFunction || "GeneratorFunction" === (ctor.displayName || ctor.name)); }, exports.mark = function (genFun) { return Object.setPrototypeOf ? Object.setPrototypeOf(genFun, GeneratorFunctionPrototype) : (genFun.__proto__ = GeneratorFunctionPrototype, define(genFun, toStringTagSymbol, "GeneratorFunction")), genFun.prototype = Object.create(Gp), genFun; }, exports.awrap = function (arg) { return { __await: arg }; }, defineIteratorMethods(AsyncIterator.prototype), define(AsyncIterator.prototype, asyncIteratorSymbol, function () { return this; }), exports.AsyncIterator = AsyncIterator, exports.async = function (innerFn, outerFn, self, tryLocsList, PromiseImpl) { void 0 === PromiseImpl && (PromiseImpl = Promise); var iter = new AsyncIterator(wrap(innerFn, outerFn, self, tryLocsList), PromiseImpl); return exports.isGeneratorFunction(outerFn) ? iter : iter.next().then(function (result) { return result.done ? result.value : iter.next(); }); }, defineIteratorMethods(Gp), define(Gp, toStringTagSymbol, "Generator"), define(Gp, iteratorSymbol, function () { return this; }), define(Gp, "toString", function () { return "[object Generator]"; }), exports.keys = function (val) { var object = Object(val), keys = []; for (var key in object) keys.push(key); return keys.reverse(), function next() { for (; keys.length;) { var key = keys.pop(); if (key in object) return next.value = key, next.done = !1, next; } return next.done = !0, next; }; }, exports.values = values, Context.prototype = { constructor: Context, reset: function reset(skipTempReset) { if (this.prev = 0, this.next = 0, this.sent = this._sent = undefined, this.done = !1, this.delegate = null, this.method = "next", this.arg = undefined, this.tryEntries.forEach(resetTryEntry), !skipTempReset) for (var name in this) "t" === name.charAt(0) && hasOwn.call(this, name) && !isNaN(+name.slice(1)) && (this[name] = undefined); }, stop: function stop() { this.done = !0; var rootRecord = this.tryEntries[0].completion; if ("throw" === rootRecord.type) throw rootRecord.arg; return this.rval; }, dispatchException: function dispatchException(exception) { if (this.done) throw exception; var context = this; function handle(loc, caught) { return record.type = "throw", record.arg = exception, context.next = loc, caught && (context.method = "next", context.arg = undefined), !!caught; } for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i], record = entry.completion; if ("root" === entry.tryLoc) return handle("end"); if (entry.tryLoc <= this.prev) { var hasCatch = hasOwn.call(entry, "catchLoc"), hasFinally = hasOwn.call(entry, "finallyLoc"); if (hasCatch && hasFinally) { if (this.prev < entry.catchLoc) return handle(entry.catchLoc, !0); if (this.prev < entry.finallyLoc) return handle(entry.finallyLoc); } else if (hasCatch) { if (this.prev < entry.catchLoc) return handle(entry.catchLoc, !0); } else { if (!hasFinally) throw new Error("try statement without catch or finally"); if (this.prev < entry.finallyLoc) return handle(entry.finallyLoc); } } } }, abrupt: function abrupt(type, arg) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.tryLoc <= this.prev && hasOwn.call(entry, "finallyLoc") && this.prev < entry.finallyLoc) { var finallyEntry = entry; break; } } finallyEntry && ("break" === type || "continue" === type) && finallyEntry.tryLoc <= arg && arg <= finallyEntry.finallyLoc && (finallyEntry = null); var record = finallyEntry ? finallyEntry.completion : {}; return record.type = type, record.arg = arg, finallyEntry ? (this.method = "next", this.next = finallyEntry.finallyLoc, ContinueSentinel) : this.complete(record); }, complete: function complete(record, afterLoc) { if ("throw" === record.type) throw record.arg; return "break" === record.type || "continue" === record.type ? this.next = record.arg : "return" === record.type ? (this.rval = this.arg = record.arg, this.method = "return", this.next = "end") : "normal" === record.type && afterLoc && (this.next = afterLoc), ContinueSentinel; }, finish: function finish(finallyLoc) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.finallyLoc === finallyLoc) return this.complete(entry.completion, entry.afterLoc), resetTryEntry(entry), ContinueSentinel; } }, "catch": function _catch(tryLoc) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.tryLoc === tryLoc) { var record = entry.completion; if ("throw" === record.type) { var thrown = record.arg; resetTryEntry(entry); } return thrown; } } throw new Error("illegal catch attempt"); }, delegateYield: function delegateYield(iterable, resultName, nextLoc) { return this.delegate = { iterator: values(iterable), resultName: resultName, nextLoc: nextLoc }, "next" === this.method && (this.arg = undefined), ContinueSentinel; } }, exports; }
function asyncGeneratorStep(gen, resolve, reject, _next, _throw, key, arg) { try { var info = gen[key](arg); var value = info.value; } catch (error) { reject(error); return; } if (info.done) { resolve(value); } else { Promise.resolve(value).then(_next, _throw); } }
function _asyncToGenerator(fn) { return function () { var self = this, args = arguments; return new Promise(function (resolve, reject) { var gen = fn.apply(self, args); function _next(value) { asyncGeneratorStep(gen, resolve, reject, _next, _throw, "next", value); } function _throw(err) { asyncGeneratorStep(gen, resolve, reject, _next, _throw, "throw", err); } _next(undefined); }); }; }

var image = document.querySelector(".company-logo img");
var cards = document.querySelectorAll(".card.colored-card");
var colorThief = new _node_modules_colorthief_dist_color_thief_mjs__WEBPACK_IMPORTED_MODULE_0__["default"]();
fetch(image.src, {
  method: "HEAD"
}).then(function (res) {
  if (res.ok) {
    var _btn = document.querySelector(".btn-custom");
    var icons = document.querySelectorAll(".colored-icon");
    var texts = document.querySelectorAll(".colored-text");
    cards.forEach( /*#__PURE__*/function () {
      var _ref = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee3(card) {
        var palette, primary;
        return _regeneratorRuntime().wrap(function _callee3$(_context3) {
          while (1) switch (_context3.prev = _context3.next) {
            case 0:
              _context3.next = 2;
              return extractColor(image);
            case 2:
              palette = _context3.sent;
              primary = palette[0].join(",");
              card.style.background = "rgba(".concat(primary, ", 0.1)");
              _btn !== null ? _btn.style.background = "rgb(".concat(primary, ")") : "";
              _btn !== null ? _btn.style.background = "rgb(".concat(primary, ")") : "";
              if (icons !== null) {
                icons.forEach( /*#__PURE__*/function () {
                  var _ref2 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee(icon) {
                    return _regeneratorRuntime().wrap(function _callee$(_context) {
                      while (1) switch (_context.prev = _context.next) {
                        case 0:
                          icon.style.background = "rgba(".concat(primary, ", 0.1)");
                          icon.style.color = "rgb(".concat(primary, ")");
                        case 2:
                        case "end":
                          return _context.stop();
                      }
                    }, _callee);
                  }));
                  return function (_x2) {
                    return _ref2.apply(this, arguments);
                  };
                }());
              }
              if (texts !== null) {
                texts.forEach( /*#__PURE__*/function () {
                  var _ref3 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee2(text) {
                    return _regeneratorRuntime().wrap(function _callee2$(_context2) {
                      while (1) switch (_context2.prev = _context2.next) {
                        case 0:
                          text.style.color = "rgb(".concat(primary, ")");
                        case 1:
                        case "end":
                          return _context2.stop();
                      }
                    }, _callee2);
                  }));
                  return function (_x3) {
                    return _ref3.apply(this, arguments);
                  };
                }());
              }
            case 9:
            case "end":
              return _context3.stop();
          }
        }, _callee3);
      }));
      return function (_x) {
        return _ref.apply(this, arguments);
      };
    }());
  } else {
    btn.classList.remove("btn-custom");
    btn.classList.add("btn-primary");
    console.log("Image does not exist.");
  }
})["catch"](function (err) {
  return console.log("Error:", err);
});
function extractColor(image) {
  return new Promise(function (resolve) {
    var getPalette = function getPalette() {
      return colorThief.getPalette(image, 4);
    };
    if (image.complete) {
      return resolve(getPalette());
    }
    image.onload = function () {
      resolve(getPalette());
    };
  });
}
/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = ({});
})();

/******/ })()
;