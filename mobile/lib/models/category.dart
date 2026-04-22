import 'package:flutter/material.dart';
import '../core/theme/app_gradients.dart';

enum NewsCategory {
  politics('Politics', 'ରାଜନୀତି'),
  sports('Sports', 'କ୍ରୀଡ଼ା'),
  crime('Crime', 'ଅପରାଧ'),
  business('Business', 'ବ୍ୟବସାୟ'),
  entertainment('Entertainment', 'ମନୋରଞ୍ଜନ'),
  education('Education', 'ଶିକ୍ଷା'),
  health('Health', 'ସ୍ୱାସ୍ଥ୍ୟ'),
  technology('Technology', 'ପ୍ରଯୁକ୍ତି');

  final String label;
  final String odiaLabel;
  const NewsCategory(this.label, this.odiaLabel);

  LinearGradient get gradient => AppGradients.forCategory(name);
}

enum NewsPriority { normal, urgent, breaking }

enum NewsStatus { draft, submitted, approved, rejected, published }
