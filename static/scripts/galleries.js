"use strict";

window.addEventListener('load', () => {
  for ( const gallery of document.querySelectorAll( '.gallery' ) ) {
    // const rem = parseFloat(getComputedStyle(document.documentElement).fontSize)
    const controls = document.querySelector('#gallery-controls-template').content.cloneNode(true)
    gallery.parentElement.insertBefore( controls, gallery.nextSibling )
    gallery.nextElementSibling.querySelector( '.right' ).onclick = () => { gallery.scroll({
      // left: gallery.scrollLeft + gallery.offsetWidth - 10 * rem,
      left: gallery.scrollLeft + 0.6 * window.innerWidth ,
      behavior: "smooth"
    })}
    gallery.nextElementSibling.querySelector( '.left' ).onclick = () => { gallery.scroll({
      // left: gallery.scrollLeft - gallery.offsetWidth + 10 * rem,
      left: gallery.scrollLeft - 0.6 * window.innerWidth,
      behavior: "smooth"
    })}
  }
})
