"use strict";(self.webpackChunk_N_E=self.webpackChunk_N_E||[]).push([[8389,3047],{82114:function(a,b,c){var d=c(93205);function e(a){a.register(d),function(a){for(var b=/[^<()"']|\((?:<expr>)*\)|<(?!#--)|<#--(?:[^-]|-(?!->))*-->|"(?:[^\\"]|\\.)*"|'(?:[^\\']|\\.)*'/.source,c=0;c<2;c++)b=b.replace(/<expr>/g,function(){return b});b=b.replace(/<expr>/g,/[^\s\S]/.source);var d={comment:/<#--[\s\S]*?-->/,string:[{pattern:/\br("|')(?:(?!\1)[^\\]|\\.)*\1/,greedy:!0},{pattern:RegExp(/("|')(?:(?!\1|\$\{)[^\\]|\\.|\$\{(?:(?!\})(?:<expr>))*\})*\1/.source.replace(/<expr>/g,function(){return b})),greedy:!0,inside:{interpolation:{pattern:RegExp(/((?:^|[^\\])(?:\\\\)*)\$\{(?:(?!\})(?:<expr>))*\}/.source.replace(/<expr>/g,function(){return b})),lookbehind:!0,inside:{"interpolation-punctuation":{pattern:/^\$\{|\}$/,alias:"punctuation"},rest:null}}}}],keyword:/\b(?:as)\b/,boolean:/\b(?:false|true)\b/,"builtin-function":{pattern:/((?:^|[^?])\?\s*)\w+/,lookbehind:!0,alias:"function"},function:/\b\w+(?=\s*\()/,number:/\b\d+(?:\.\d+)?\b/,operator:/\.\.[<*!]?|->|--|\+\+|&&|\|\||\?{1,2}|[-+*/%!=<>]=?|\b(?:gt|gte|lt|lte)\b/,punctuation:/[,;.:()[\]{}]/};d.string[1].inside.interpolation.inside.rest=d,a.languages.ftl={"ftl-comment":{pattern:/^<#--[\s\S]*/,alias:"comment"},"ftl-directive":{pattern:/^<[\s\S]+>$/,inside:{directive:{pattern:/(^<\/?)[#@][a-z]\w*/i,lookbehind:!0,alias:"keyword"},punctuation:/^<\/?|\/?>$/,content:{pattern:/\s*\S[\s\S]*/,alias:"ftl",inside:d}}},"ftl-interpolation":{pattern:/^\$\{[\s\S]*\}$/,inside:{punctuation:/^\$\{|\}$/,content:{pattern:/\s*\S[\s\S]*/,alias:"ftl",inside:d}}}},a.hooks.add("before-tokenize",function(c){var d=RegExp(/<#--[\s\S]*?-->|<\/?[#@][a-zA-Z](?:<expr>)*?>|\$\{(?:<expr>)*?\}/.source.replace(/<expr>/g,function(){return b}),"gi");a.languages["markup-templating"].buildPlaceholders(c,"ftl",d)}),a.hooks.add("after-tokenize",function(b){a.languages["markup-templating"].tokenizePlaceholders(b,"ftl")})}(a)}a.exports=e,e.displayName="ftl",e.aliases=[]},93205:function(a){function b(a){!function(a){function b(a,b){return"___"+a.toUpperCase()+b+"___"}Object.defineProperties(a.languages["markup-templating"]={},{buildPlaceholders:{value:function(c,d,e,f){if(c.language===d){var g=c.tokenStack=[];c.code=c.code.replace(e,function(a){if("function"==typeof f&&!f(a))return a;for(var e,h=g.length;-1!==c.code.indexOf(e=b(d,h));)++h;return g[h]=a,e}),c.grammar=a.languages.markup}}},tokenizePlaceholders:{value:function(c,d){if(c.language===d&&c.tokenStack){c.grammar=a.languages[d];var e=0,f=Object.keys(c.tokenStack);g(c.tokens)}function g(h){for(var i=0;i<h.length&&!(e>=f.length);i++){var j=h[i];if("string"==typeof j||j.content&&"string"==typeof j.content){var k=f[e],l=c.tokenStack[k],m="string"==typeof j?j:j.content,n=b(d,k),o=m.indexOf(n);if(o> -1){++e;var p=m.substring(0,o),q=new a.Token(d,a.tokenize(l,c.grammar),"language-"+d,l),r=m.substring(o+n.length),s=[];p&&s.push.apply(s,g([p])),s.push(q),r&&s.push.apply(s,g([r])),"string"==typeof j?h.splice.apply(h,[i,1].concat(s)):j.content=s}}else j.content&&g(j.content)}return h}}}})}(a)}a.exports=b,b.displayName="markupTemplating",b.aliases=[]}}])