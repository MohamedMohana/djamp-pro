/**
 * Template Stepper
 */

'use strict';

(function () {
  // Init custom option check
  window.Helpers.initCustomOptionCheck();

  // Bootstrap Stepper
  // --------------------------------------------------------------------
  const wizardNumbered = document.querySelector('.wizard-numbered');
  if (wizardNumbered) {
    const wizardNumberedBtnNextList = [].slice.call(wizardNumbered.querySelectorAll('.btn-next')),
      wizardNumberedBtnPrevList = [].slice.call(wizardNumbered.querySelectorAll('.btn-prev')),
      wizardNumberedBtnSubmit = wizardNumbered.querySelector('.btn-submit');

    const numberedStepper = new Stepper(wizardNumbered, {
      linear: true
    });
    if (wizardNumberedBtnNextList) {
      wizardNumberedBtnNextList.forEach(wizardNumberedBtnNext => {
        wizardNumberedBtnNext.addEventListener('click', event => {
          numberedStepper.next();
        });
      });
    }
    if (wizardNumberedBtnPrevList) {
      wizardNumberedBtnPrevList.forEach(wizardNumberedBtnPrev => {
        wizardNumberedBtnPrev.addEventListener('click', event => {
          numberedStepper.previous();
        });
      });
    }
    if (wizardNumberedBtnSubmit) {
      wizardNumberedBtnSubmit.addEventListener('click', event => {
        alert('Submitted..!!');
      });
    }
  }
})();